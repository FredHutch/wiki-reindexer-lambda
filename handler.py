import json
import os
import stat
import subprocess
import tempfile

import elasticsearch
import scrapy
import sh

import boto3
from aws_requests_auth.aws_auth import AWSRequestsAuth
from elasticsearch import Elasticsearch, RequestsHttpConnection


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


def hello(event, context):
    infile = tempfile.mkstemp()
    outfile = tempfile.mkstemp()
    with open(infile[1], "w") as infh:
        infh.write("<p>i am some text</p>")
    os.environ["PATH"] += ":/opt"
    sh.pandoc(
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
    output = None
    with open(outfile[1]) as outfh:
        output = outfh.read()
    out = sh.echo("hello", _tty_out=False, _tty_in=False)

    body = {
        "message": "Go Serverless v1.0! Your function executed successfully!",
        "log": os.listdir("/opt"),
        "sh_retcode": out.exit_code,
        "retcode": subprocess.run(["ls"]).returncode,
        "input": event,
        "output": output,
        "es_info": get_es_info(),
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
