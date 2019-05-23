"""
lambda handlers
"""


import json
import sys

import boto3

import crawl_wiki


def push_hook(event, context):  # pylint: disable=unused-argument
    "handler for github push hook"

    lam = boto3.client("lambda")
    funcs = lam.list_functions(MaxItems=999)
    ourfunc = [
        x["FunctionName"]
        for x in funcs["Functions"]
        if "run_crawler" in x["FunctionName"]
    ][0]
    print("found function {}".format(ourfunc))
    # event_obj = JSON.parse(event.body)
    # event_obj["called_from_push_hook"] = True
    # TODO - pass along the event from github so that
    # the function knows more about the push (like,
    # if there were no commits to the master branch
    # we don' have to do anything).
    result = lam.invoke(
        FunctionName=ourfunc,
        InvocationType="Event",
        Payload=json.dumps(dict(invoked_from_push_hook=True)),
    )
    print("result was {}".format(result))
    del result["Payload"]

    body = {
        "message": "Go Serverless v1.0! Your function executed successfully!",
        "input": event,
        "output": json.dumps(result),
    }

    response = {"statusCode": 200, "body": json.dumps(body)}

    return response


def run_crawler(event, context):  # pylint: disable=unused-argument
    "handler to start crawler"

    print("were we called from push_hook?")
    if "called_from_push_hook" in event:
        # TODO sleep a bit
        print("yes")
    else:
        print("no")

    body = {
        "message": "Go Serverless v1.0! Your function executed successfully!",
        "input": event,
        "crawl_result": crawl_wiki.main(),
    }

    response = {"statusCode": 200, "body": json.dumps(body)}
    print("this is the response we would return if we were returning something:")
    print(response)
    # TODO  exit with a different code if there's an error?
    # This is really not ideal.
    # TODO look into using crochet. 
    # https://stackoverflow.com/questions/42388541/scrapy-throws-error-reactornotrestartable-when-runnning-on-aws-lambda
    # https://stackoverflow.com/questions/41495052/scrapy-reactor-not-restartable
    sys.exit(0)
    # return response
