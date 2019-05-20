
import json
import os
import stat
import subprocess

import elasticsearch
import scrapy
import sh




def hello(event, context):
    # out = sh.echo("hello")
    body = {
        "message": "Go Serverless v1.0! Your function executed successfully!",
        "log": os.listdir("/opt"),
        "retcode": subprocess.run(["ls"]).returncode,
        "perms": oct(os.stat("/opt/pandoc")[stat.ST_MODE]),
        "input": event
    }

    response = {
        "statusCode": 200,
        "body": json.dumps(body)
    }

    return response

    # Use this code if you don't use the http event with the LAMBDA-PROXY
    # integration
    """
    return {
        "message": "Go Serverless v1.0! Your function executed successfully!",
        "event": event
    }
    """
