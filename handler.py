"""
lambda handlers
"""


import json
import time

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
    # if there were no commits to the main branch
    # we don't have to do anything).
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
        print("yes")
        print("Sleeping for a bit.")
        time.sleep(5 * 60)
        print("Woke up feeling refreshed.")
    else:
        print("no")

    body = {
        "message": "Go Serverless v1.0! Your function executed successfully!",
        "input": event,
        "crawl_result": crawl_wiki.main(),
    }

    return {"statusCode": 200, "body": json.dumps(body)}


def delete_orphans(event, context):  # pylint: disable=unused-argument
    "delete items from index that are no longer on site"

    body = {
        "message": "Go Serverless v1.0! Your function executed successfully!",
        "input": event,
        "orphans_deleted": crawl_wiki.delete_orphans(),
    }

    return {"statusCode": 200, "body": json.dumps(body)}
