#!/bin/env python2.7

import sys
import os
import time
import datetime
import json
from subprocess import call

import boto3
s3 = boto3.resource("s3")
cf = boto3.client('cloudformation')
lam = boto3.client('lambda')


""" Configuration from baws.env """
SUPPORT_BUCKET_NAME = os.getenv("SUPPORT_BUCKET_NAME")
APP_NAME = os.getenv("APP_NAME")
DEPLOYMENT_NAME = os.getenv("DEPLOYMENT_NAME")

if not os.getenv("BAWS_SOURCED"):
    raise Exception("Please source baws.env before running this script.")


if not len(sys.argv) == 2 or not sys.argv[1]:
    raise Exception("First parameter should be a lambda function name")


""" Setup """


# physical lambda name will also contain cf id, # so it's guarranteed to be unique across deployments
LAMBDA_NAME = sys.argv[1]
LAMBDA_DIR = os.path.join(".", "lambdas", LAMBDA_NAME)
LAMBDA_CONFIG = json.load(
    open(os.path.join(LAMBDA_DIR, "config.json")),
    "utf-8")

ZIP_PATH = os.path.join("..", "{}.zip".format(LAMBDA_NAME))
ZIP_FILE = os.path.join(LAMBDA_DIR, ZIP_PATH)

STACK_NAME = ''.join([DEPLOYMENT_NAME, '-', 'l', LAMBDA_NAME])


""" Zip the lambda """

call(["rm", ZIP_FILE])
call("chmod -Rv a=rX,u+w *", cwd=LAMBDA_DIR, shell=True)
call(["zip", ZIP_PATH, "-r", ".", "-i", "*"], cwd=LAMBDA_DIR)


""" Upload the zipfile to s3 """

S3_KEY = "{}-{}.zip".format(LAMBDA_NAME, int(time.time()))
zipFileObject = s3.Object(SUPPORT_BUCKET_NAME, S3_KEY)
zipFileObject.put(Body=open(ZIP_FILE))


# Example configuration:
# {u'roleStatements': [{u'Action': u'*', u'Resource': u'*',
#   u'Effect': u'Allow'}], u'handler': u'lambda_handler',
#   u'runtime': u'python2.7', u'memorySize': 256, u'timeout': 5}

CF_LAMBDA_NAME = "".join(["Fn", LAMBDA_NAME])
CF_ROLE_NAME = "".join(["RoleForLambda", LAMBDA_NAME])
CF_ROLEPOLICIES_NAME = "".join([CF_ROLE_NAME, "Policies"])
CF_TEMPLATE = {
    "AWSTemplateFormatVersion": "2010-09-09",
    "Resources": {
        CF_ROLE_NAME: {
            "Type": "AWS::IAM::Role",
            "Properties": {
                "AssumeRolePolicyDocument": {
                    "Version": "2012-10-17",
                    "Statement": [{
                        "Effect": "Allow",
                        "Principal": {
                            "Service": ["lambda.amazonaws.com"]
                        },
                        "Action": ["sts:AssumeRole"]
                    }]
                },
                "Path": "/"
            }
        },
        CF_ROLEPOLICIES_NAME: {
            "Type": "AWS::IAM::Policy",
            "Properties": {
                "PolicyName": "root",
                "PolicyDocument": {
                    "Version": "2012-10-17",
                    "Statement": LAMBDA_CONFIG[u"roleStatements"]
                },
                "Roles": [{
                    "Ref": CF_ROLE_NAME
                }]
            }
        },
        CF_LAMBDA_NAME: {
            "Type": "AWS::Lambda::Function",
            "Properties": {
                "Code": {"S3Bucket": SUPPORT_BUCKET_NAME, "S3Key": S3_KEY},
                "Description": "Deployed {}".format(datetime.datetime.now()),
                "Handler": LAMBDA_CONFIG[u"handler"],
                "MemorySize": LAMBDA_CONFIG[u"memorySize"],
                "Role": {"Fn::GetAtt": [CF_ROLE_NAME, "Arn"]},
                "Runtime": LAMBDA_CONFIG[u"runtime"],
                "Timeout": LAMBDA_CONFIG[u"timeout"]
            }
        }
    }
}


try:
    print "Updating stack"
    create = False
    cf.list_stack_resources(StackName=STACK_NAME)
except Exception, e:
    print "Creating new stack"
    create = True

if create:
    response = cf.create_stack(
        StackName=STACK_NAME,
        TemplateBody=json.dumps(CF_TEMPLATE),
        Capabilities=['CAPABILITY_IAM'],
    )
else:
    response = cf.update_stack(
        StackName=STACK_NAME,
        TemplateBody=json.dumps(CF_TEMPLATE),
        Capabilities=['CAPABILITY_IAM'],
    )


print "Updating", response[u"StackId"]

while True:
    stackInfo = cf.describe_stacks(StackName=STACK_NAME)["Stacks"][0]
    status = stackInfo["StackStatus"]

    if status == 'CREATE_IN_PROGRESS' or status == 'UPDATE_IN_PROGRESS':
        time.sleep(5)
    else:
        break

print " ".join(["StackStatus:", status,
                "with message =", str(stackInfo.get("StackStatusReason"))])


resources = cf.describe_stack_resources(StackName=STACK_NAME)["StackResources"]
lambdas = lam.list_functions()["Functions"]


for resource in resources:
    if resource["ResourceType"] == "AWS::Lambda::Function":
        lambdaDetails = filter(lambda fn: fn["FunctionName"] == resource["PhysicalResourceId"],
                               lambdas)[0]
        resource["FunctionArn"] = lambdaDetails["FunctionArn"]


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, datetime.datetime):
        serial = obj.isoformat()
        return serial
    raise TypeError("Type not serializable")


RESOURCES_FILE_NAME = os.path.join('.', 'resources', 'default-deployment', 'lambda-resources.json')
json.dump(resources, open(RESOURCES_FILE_NAME, 'w'), default=json_serial, indent=2, sort_keys=True)
print "Wrote resource descriptors to", RESOURCES_FILE_NAME
