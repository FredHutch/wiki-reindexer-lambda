import json
import os
import stat
import subprocess
import tempfile
import time

import elasticsearch
import scrapy
import sh

import boto3
from aws_requests_auth.aws_auth import AWSRequestsAuth
from elasticsearch import Elasticsearch, RequestsHttpConnection

import crawl_wiki

def get_es_info():
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
    es = Elasticsearch(
        hosts=[{"host": es_host, "port": 443}],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
    )
    return es.info()



def push_hook(event, context):
    "handler for github push hook"

    print("hello, sleeping for a while")
    time.sleep(1) # TODO sleep for like 5 mins to allow jekyll to build
    print("i am awake now!")
    lam = boto3.client("lambda")
    funcs = lam.list_functions(MaxItems=999)
    ourfunc = [x['FunctionName'] for x in funcs['Functions'] if "wiki-reindexer" in x['FunctionName']][0]
    result = lambda.invoke(FunctionName=ourfunc, InvocationType='Event')
    print("result was {}".format(result))
    response = {"statusCode": 200, "body": json.dumps(body)}


    body = {
        "message": "Go Serverless v1.0! Your function executed successfully!",
        "input": event,
        "output": response,
    }


    return response


def run_crawler(event, context):
    "handler to start crawler"
    body = {
        "message": "Go Serverless v1.0! Your function executed successfully!",
        "input": event,
        "crawl_result": crawl_wiki.main()
    }

    response = {"statusCode": 200, "body": json.dumps(body)}

    return response

    # Use this code if you don't use the http event with the LAMBDA-PROXY
    # integration
    """
    return {
        "message": "Go Serverless v1.0! Your function executed successfully!",
        "event": event
    }
    """
