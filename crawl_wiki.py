"""
Crawls the wiki, generating URLs and
page titles for each page.
"""

import importlib
from multiprocessing import Process, Pipe
import os
import re
from urllib.parse import urlparse
import sys
import tempfile
import traceback

from aws_requests_auth.aws_auth import AWSRequestsAuth
import boto3
from elasticsearch.helpers import bulk
from elasticsearch import Elasticsearch, RequestsHttpConnection, ElasticsearchException
import scrapy
import scrapy.crawler
import scrapy.settings
import sh

SPEC = importlib.util.spec_from_file_location("_sqlite3", "/dummysqllite.py")
sys.modules["_sqlite3"] = importlib.util.module_from_spec(SPEC)
sys.modules["sqlite3"] = importlib.util.module_from_spec(SPEC)
sys.modules["sqlite3.dbapi2"] = importlib.util.module_from_spec(SPEC)

INDEX_NAME = (
    "sciwiki0"
)  # sciwiki0 is the production index, use sciwiki-test for testing
  


def ireplace(old, repl, text):
    "case-insensitive replace"
    return re.sub("(?i)" + re.escape(old), lambda m: repl, text)


def html_to_text(html):
    "convert html to text"
    infile = tempfile.mkstemp()
    with open(infile[1], "w") as in_fh:
        in_fh.write(html)
    outfile = tempfile.mkstemp()

    pandoc_result = sh.pandoc(
        "-f",
        "html",
        "-t",
        "plain",
        "-o",
        outfile[1],
        infile[1],
        _tty_out=False,
        _tty_in=False,
    )
    print("exit code is {}".format(pandoc_result.exit_code))
    with open(outfile[1]) as outfh:
        output = outfh.read()
    os.remove(infile[1])
    os.remove(outfile[1])
    return output


class WikiSpider(scrapy.Spider):
    "spider class"
    name = "sciwiki"
    start_urls = ["https://sciwiki.fredhutch.org"]
    documents = []
    urldict = {}

    def parse(self, response):
        url_str = response.url
        url = urlparse(url_str).path
        if url == "":
            url = "/"

        try:
            titles = response.css("title")
        except scrapy.exceptions.NotSupported:
            # message "Response content isn't text" means this is a binary file or something
            print("In except clause")
            return

        body = response.body.decode("utf-8")
        text = html_to_text(body)

        for title in titles:  # really there should only be one.
            tstr = title.get()
            tstr = ireplace("<title>", "", tstr)
            tstr = ireplace("</title>", "", tstr)
            tstr = tstr.replace(" - Fred Hutch Biomedical Data Science Wiki", "")
            tstr = tstr.strip()

            self.documents.append({"title": tstr, "url": url, "content": text})
            yield {"title": tstr, "url": url, "content": text}

        for item in response.css('a::attr("href")'):
            npurl = item.get()
            if npurl is None:
                continue
            npurl = npurl.strip()
            # NOTE: This will exclude absolute links back to the site,
            # but hopefully we don't have any of those.
            if ":" in npurl:
                print("excluded absolute link {}".format(npurl))
                continue
            if npurl.startswith("#"):
                continue
            if not npurl in self.urldict:
                self.urldict[npurl] = 1
                yield response.follow(item, self.parse)


def do_crawl(conn):
    "do the crawl"
    try:
        url = "https://sciwiki.fredhutch.org/contributors/dtenenba/"
        crawler = scrapy.crawler.CrawlerProcess(
            {
                "USER_AGENT": "Dan Tenenbaum (+{})".format(url),
                "FEED_URI": "/tmp/results.json",
            }
        )
        wks = WikiSpider()
        crawler.crawl(wks)
        crawler.start()
        print("in do_crawl, number of docs is {}".format(len(wks.documents)))
        conn.send(wks.documents)
        conn.close()
    except:  # pylint: disable=bare-except
        print("FATAL: do_crawl() exited while multiprocessing")
        traceback.print_exc()


def get_list_of_ids():
    "gets list of all IDs in the index"
    conn = get_elasticsearch_connection()
    body = dict(query=dict(match_all=dict()))
    # bizarre pylint false positive.
    # related to https://www.logilab.org/ticket/73813 ?
    resp = conn.search(  # pylint: disable=unexpected-keyword-arg
        index=INDEX_NAME,
        docvalue_fields=["_id"],
        stored_fields="_none_",
        size=5000,
        body=body,
    )
    return [x["_id"] for x in resp["hits"]["hits"]]


def get_elasticsearch_connection():
    "gets an aws-authenticated elasticsearch connection"
    session = boto3.session.Session()
    credentials = session.get_credentials().get_frozen_credentials()
    es_host = (
        "search-sciwiki-search-0-f7ntx2mpc5g6yohp6dtiwzsdiy.us-west-2.es.amazonaws.com"
    )
    awsauth = AWSRequestsAuth(
        aws_access_key=credentials.access_key,
        aws_secret_access_key=credentials.secret_key,
        aws_token=credentials.token,
        aws_host=es_host,
        aws_region=session.region_name,
        aws_service="es",
    )
    return Elasticsearch(
        hosts=[{"host": es_host, "port": 443}],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
    )


def delete_orphans():
    "delete items in index that are no longer on site"
    site_urls = main(True)
    # Velocity/sanity check:
    if not site_urls:
        return "error! no site urls, refusing to remove all documents!"

    index_urls = get_list_of_ids()
    orphans = list(set(index_urls) - set(site_urls))
    if not orphans:
        print("no orphans!")
        return []
    els = get_elasticsearch_connection()
    outer = []
    for orphan in orphans:
        temp = dict(_id=orphan, _index=INDEX_NAME, _type="document", _op_type="delete")
        outer.append(temp)
        # res = els.delete(index=crawl_wiki.INDEX_NAME, id=orphan, doc_type="document")
    print("number of site urls: {}".format(len(set(site_urls))))
    print("number of index urls: {}".format(len(set(index_urls))))

    bulk(els, outer)
    return orphans
    # return []  # TODO delete me


def main(urls_only=False):
    "do the work"
    os.environ["PATH"] += ":/opt"
    parent_conn, child_conn = Pipe()
    proc = Process(target=do_crawl, args=(child_conn,))
    proc.start()
    docs = parent_conn.recv()
    proc.join()

    if urls_only:
        return [x["url"] for x in docs]

    outer = []

    for item in docs:
        doc_id = item["url"]
        del item["url"]
        # no need for _op_type below; default is to index (if doc exists) or
        # create (if not). https://stackoverflow.com/q/32133472/470769
        temp = dict(_id=doc_id, _index=INDEX_NAME, _type="document", _source=item)
        outer.append(temp)

    els = get_elasticsearch_connection()

    try:
        retval = bulk(els, outer)
        print("bulking was successful")
        print(retval)
        return retval
    except ElasticsearchException as exc:
        print("caught exception when bulking up")
        print(exc)
        return str(exc)


if __name__ == "__main__":
    main()
