"""
Crawls the wiki, generating URLs and
page titles for each page.

Run me with:

scrapy runspider -o out.json -t json crawl_wiki.py
"""

import io
import re
from urllib.parse import urlparse
import sys


import elasticsearch
from elasticsearch.exceptions import TransportError
from elasticsearch.helpers import bulk, streaming_bulk

import scrapy
import scrapy.crawler
import scrapy.settings

import sh

def ireplace(old, repl, text):
    return re.sub('(?i)'+re.escape(old), lambda m: repl, text)


urldict = dict()

def html_to_text(html):
    "convert html to text"
    stdout = io.StringIO()
    stdin = io.StringIO(html)
    args = dict(_in=stdin, _out=stdout)
    result = sh.pandoc("-f", "html", "-t", "plain", _in=stdin, _out=stdout)
    print("exit code is {}".format(result.exit_code))
    return stdout.getvalue()

class WikiSpider(scrapy.Spider):
    name = 'sciwiki'
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
            titles = response.css('title')
        except scrapy.exceptions.NotSupported as exc:
            # message "Response content isn't text" means this is a binary file or something
            print("In except clause")
            return

        body = response.body.decode('utf-8')
        text = html_to_text(body)

        for title in titles: # really there should only be one.
            tstr = title.get()# 'data'
            tstr = ireplace("<title>", "", tstr)
            tstr = ireplace("</title>", "", tstr)
            tstr = tstr.replace(" - Fred Hutch Biomedical Data Science Wiki", "")
            tstr = tstr.strip()

            self.documents.append({
                'title': tstr,
                'url': url,
                'content': text,
            })
            yield {
                'title': tstr,
                'url': url,
                'content': text,
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
            if not npurl in urldict:
                urldict[npurl] = 1
                yield response.follow(item, self.parse)

if __name__ == "__main__":
    # settings = scrapy.settings.Settings()
    # settings.set("USER_AGENT", "Dan Tenenbaum (+https://sciwiki.fredhutch.org/contributors/dtenenba/)")
    # crawler = scrapy.crawler.Crawler(WikiSpider(), settings)

    # crawler.crawl(WikiSpider())
    # crawler.start()

    c = scrapy.crawler.CrawlerProcess({
        'USER_AGENT': "Dan Tenenbaum (+https://sciwiki.fredhutch.org/contributors/dtenenba/)"
    })

    ws = WikiSpider()
    c.crawl(ws)
    c.start()

    es = elasticsearch.Elasticsearch([{'host': 'search-sciwiki-search-0-f7ntx2mpc5g6yohp6dtiwzsdiy.us-west-2.es.amazonaws.com', 'port': 80}])
    outer = []

    for item in ws.documents:
        id = item['url']
        del item['url']
        temp = dict(_id= id, _index="sciwiki0", _op_type="create", _type="document", _source=item)
        outer.append(temp)
    
    try:
        result = bulk(es, outer)
    except Exception as exc:
        print("caught exception when bulking up")
        print(exc)

    import IPython;IPython.embed()
