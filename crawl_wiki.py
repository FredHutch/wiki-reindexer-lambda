"""
Crawls the wiki, generating URLs and
page titles for each page.

Run me with:

scrapy runspider -o out.json -t json crawl_wiki.py
"""

# import imp # NOTE deprecated in favor of importlib TODO FIX
import importlib
import os
import re
from urllib.parse import urlparse
import sys
import tempfile

# sys.modules["_sqlite"] = imp.new_module("_sqlite")

spec = importlib.util.spec_from_file_location("_sqlite3","/dummysqllite.py")
sys.modules["_sqlite3"] = importlib.util.module_from_spec(spec)
sys.modules["sqlite3"] = importlib.util.module_from_spec(spec)
sys.modules["sqlite3.dbapi2"] = importlib.util.module_from_spec(spec)

from aws_requests_auth.aws_auth import AWSRequestsAuth
import boto3
from elasticsearch.helpers import bulk
from elasticsearch import Elasticsearch, RequestsHttpConnection, ElasticsearchException
import scrapy
import scrapy.crawler
import scrapy.settings
import sh


def ireplace(old, repl, text):
    "case-insensitive replace"
    return re.sub("(?i)" + re.escape(old), lambda m: repl, text)


URLDICT = dict()


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
    start_urls = [
        # 'http://localhost:8000',
        "https://sciwiki.fredhutch.org"
    ]
    documents = []

    def parse(self, response):
        print("in parse")
        url_str = response.url
        print("url is {}".format(url_str))
        url = urlparse(url_str).path
        if url == "":
            url = "/"

        # print(response.url)
        print("on page {}".format(str(response)))

        try:
            titles = response.css("title")
            print("got title {}".format(titles))
        except scrapy.exceptions.NotSupported:
            # message "Response content isn't text" means this is a binary file or something
            print("In except clause")
            return

        print("trying to get body")
        body = response.body.decode("utf-8")
        print("got body")
        text = html_to_text(body)
        print("converted body to text")

        print("len of titles is {}".format(len(titles)))
        for title in titles:  # really there should only be one.
            tstr = title.get()  # 'data'
            tstr = ireplace("<title>", "", tstr)
            tstr = ireplace("</title>", "", tstr)
            tstr = tstr.replace(" - Fred Hutch Biomedical Data Science Wiki", "")
            tstr = tstr.strip()

            self.documents.append({"title": tstr, "url": url, "content": text})
            yield {
                "title": tstr,
                "url": url,
                "content": text,
                # 'author': quote.xpath('span/small/text()').get(),
            }

        for item in response.css('a::attr("href")'):
            npurl = item.get()
            print("next page url is {}".format(npurl) )
            if npurl is None:
                print("npurl is none")
                continue
            npurl = npurl.strip()
            # NOTE: This will exclude absolute links back to the site,
            # but hopefully we don't have any of those.
            if ":" in npurl:
                print("excluded absolute link {}".format(npurl))
                continue
            if npurl.startswith("#"):
                print("HODAD!!!!")
                continue
            print("url is {}".format(npurl))
            if not npurl in URLDICT:
                print("found a new url to index")
                URLDICT[npurl] = 1
                yield response.follow(item, self.parse)


def main():
    "do the work"
    print("in main")
    os.environ['PATH'] += ":/opt"
    crawler = scrapy.crawler.CrawlerProcess(
        {
            "USER_AGENT": "Dan Tenenbaum (+https://sciwiki.fredhutch.org/contributors/dtenenba/)",
            "FEED_URI": "/tmp/results.json",
        }
    )

    wks = WikiSpider()
    print("got wks")
    crawlres = crawler.crawl(wks)
    print("called crawl() with result {}".format(crawlres))
    crawler.start()
    print("called start()")

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
    els = Elasticsearch(
        hosts=[{"host": es_host, "port": 443}],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
    )
    print("created els")

    outer = []

    for item in wks.documents:
        doc_id = item["url"]
        del item["url"]
        # no need for _op_type below; default is to index (if doc exists) or
        # create (if not). https://stackoverflow.com/q/32133472/470769
        # 'real' index is sciwiki0, TODO be sure and change it back!
        temp = dict(_id=doc_id, _index="sciwiki-test", _type="document", _source=item)
        outer.append(temp)

    print("len of outer is {}".format(len(outer)))

    print("about to bulk up")
    try:
        retval =  bulk(els, outer)
        print("bulking was successful")
        print(retval)
        return retval
    except ElasticsearchException as exc:
        print("caught exception when bulking up")
        print(exc)
        return str(exc)


if __name__ == "__main__":
    main()
