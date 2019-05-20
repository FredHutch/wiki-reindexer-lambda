
import json
import os

import elasticsearch
import scrapy
import sh




def hello(event, context):
    body = {
        "message": "Go Serverless v1.0! Your function executed successfully!",
        "log": os.listdir("/opt"),
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
