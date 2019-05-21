"""
Crawls the wiki, generating URLs and
page titles for each page.

Run me with:

scrapy runspider -o out.json -t json crawl_wiki.py
"""

import re
from urllib.parse import urlparse
import tempfile

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
        url_str = response.url
        url = urlparse(url_str).path
        if url == "":
            url = "/"

        # print(response.url)
        print("on page {}".format(str(response)))

        try:
            titles = response.css("title")
        except scrapy.exceptions.NotSupported:
            # message "Response content isn't text" means this is a binary file or something
            print("In except clause")
            return

        body = response.body.decode("utf-8")
        text = html_to_text(body)

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
            if npurl is None:
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
                URLDICT[npurl] = 1
                yield response.follow(item, self.parse)


def main():
    "do the work"
    crawler = scrapy.crawler.CrawlerProcess(
        {
            "USER_AGENT": "Dan Tenenbaum (+https://sciwiki.fredhutch.org/contributors/dtenenba/)"
        }
    )

    wks = WikiSpider()
    crawler.crawl(wks)
    crawler.start()

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

    outer = []

    for item in wks.documents:
        doc_id = item["url"]
        del item["url"]
        # no need for _op_type below; default is to index (if doc exists) or
        # create (if not). https://stackoverflow.com/q/32133472/470769
        # 'real' index is sciwiki0, TODO be sure and change it back!
        temp = dict(_id=doc_id, _index="sciwiki-test", _type="document", _source=item)
        outer.append(temp)

    try:
        bulk(els, outer)
    except ElasticsearchException as exc:
        print("caught exception when bulking up")
        print(exc)


if __name__ == "__main__":
    main()
