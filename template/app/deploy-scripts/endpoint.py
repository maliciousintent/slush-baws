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
apig = boto3.client('apigateway')


if not len(sys.argv) == 2 or not sys.argv[1]:
    raise Exception("First parameter should be a ENDPOINT name")


""" Util methods """


def readTemplate(val, key):
    if val.find("<./") != 0:
        return val

    fileName = val.replace("<./", "")
    # print "----> reading template content from VTL file", fileName
    return open(os.path.join("endpoints", "templates", fileName)).read()


def mapTemplateValues(obj):
    ret = {}
    for key, val in obj.iteritems():
        ret[key] = readTemplate(val, key)
    return ret


""" Setup """

ENDPOINT_NAME = sys.argv[1]
ENDPOINT_DIR = os.path.join(".", "endpoints", ENDPOINT_NAME)
ENDPOINT_CONFIG = json.load(
    open(os.path.join(ENDPOINT_DIR, "config.json")),
    "utf-8")

RESTAPI_CONFIG = json.load(  # name, id
    open(os.path.join(".", "resources", "default-deployment", "api.json")),
    "utf-8")

resources = apig.get_resources(restApiId=RESTAPI_CONFIG['id'], limit=500)['items']

print "Deploying endpoint", ENDPOINT_NAME
print "--> building resource inventory..."

try:
    ROOT = filter(lambda r: r['path'] == u'/', resources)[0]
except IndexError, e:
    raise Exception("""Cannot find root Resource. This should not happen.
                    Inspect your API from the console.""")


PATH_TOKENS = ENDPOINT_CONFIG['path'].split('/')[1:]
PATH_PART = PATH_TOKENS[-1]

last_root = ROOT
for part in PATH_TOKENS:

    last_path = last_root['path']
    if len(last_path) == 1:
        last_path = ""  # root path has a trailing /, strip it!

    full_path = u''.join([last_path, "/", part])
    found_resources = filter(lambda r: r['path'] == full_path, resources)
    if found_resources:
        print "----> found existing sub-Resource with path =", full_path
        new_resource = found_resources[0]

    else:
        print "----> creating new sub-Resource with path =", full_path
        new_resource = apig.create_resource(
            restApiId=RESTAPI_CONFIG['id'],
            parentId=last_root['id'],
            pathPart=part
        )

    last_root = new_resource

resource_id = last_root['id']


try:
    print "--> deleting method", ENDPOINT_CONFIG['method']
    apig.delete_method(
        restApiId=RESTAPI_CONFIG['id'],
        resourceId=resource_id,
        httpMethod=ENDPOINT_CONFIG['method']
    )

except Exception, e:
    print "----> method did not exist"


apig.put_method(
    restApiId=RESTAPI_CONFIG['id'],
    resourceId=resource_id,
    httpMethod=ENDPOINT_CONFIG['method'],
    authorizationType='NONE',
    apiKeyRequired=False,
    requestParameters=ENDPOINT_CONFIG['requestParameters'],
    requestModels=ENDPOINT_CONFIG['requestModels']
)
print "--> put method", ENDPOINT_CONFIG['method']

for methodResponseKey, methodResponseConfig in ENDPOINT_CONFIG['methodResponses'].iteritems():
    apig.put_method_response(
        restApiId=RESTAPI_CONFIG['id'],
        resourceId=resource_id,
        httpMethod=ENDPOINT_CONFIG['method'],
        statusCode=methodResponseConfig['statusCode'],
        responseModels=methodResponseConfig['responseModels'],
    )
    print "--> put method response", methodResponseConfig['statusCode']


# prepare put_integration parameters
requestTemplates = mapTemplateValues(ENDPOINT_CONFIG['methodIntegration']['requestTemplates'])

if ENDPOINT_CONFIG['methodIntegration']['type'] == "Lambda":
    RESOURCES_FILE_NAME = os.path.join('.', 'resources', 'default-deployment', 'lambda-resources.json')
    LAMBDAS_DESCRIPTORS = json.load(open(RESOURCES_FILE_NAME))

    try:
        myLambdaArn = filter(lambda fn: fn["LogicalResourceId"] == ENDPOINT_CONFIG['methodIntegration']['uri'],
                             LAMBDAS_DESCRIPTORS)[0]["FunctionArn"]

        ENDPOINT_CONFIG['methodIntegration']['credentials'] = RESTAPI_CONFIG['apigRoleArn']
        ENDPOINT_CONFIG['methodIntegration']['type'] = 'AWS'
        ENDPOINT_CONFIG['methodIntegration']['httpMethod'] = 'POST'
        ENDPOINT_CONFIG['methodIntegration']['uri'] = "/".join([
            "arn:aws:apigateway:eu-west-1:lambda:path", "2015-03-31", "functions",
            myLambdaArn,
            "invocations"
        ])

    except Exception, e:
        print "Cannot find lambda with LogicalID", ENDPOINT_CONFIG['methodIntegration']['uri']
        print "Make sure you prepended `Fn` to the uri in the config.json file of your endpoint."
        print "Please inspect your resources from the AWS CF console."
        raise e


apig.put_integration(
    restApiId=RESTAPI_CONFIG['id'],
    resourceId=resource_id,
    httpMethod=ENDPOINT_CONFIG['method'],
    type=ENDPOINT_CONFIG['methodIntegration']['type'],
    credentials=ENDPOINT_CONFIG['methodIntegration']['credentials'],  # required for AWS integrations
    integrationHttpMethod=ENDPOINT_CONFIG['methodIntegration']['httpMethod'],
    uri=ENDPOINT_CONFIG['methodIntegration']['uri'],
    requestParameters=ENDPOINT_CONFIG['methodIntegration']['requestParameters'],
    requestTemplates=requestTemplates,
)
print "--> put method integration with type =", ENDPOINT_CONFIG['methodIntegration']['type']


for integrationResponseKey, integrationResponeConfig in ENDPOINT_CONFIG['methodIntegration']['integrationResponses'].iteritems():
    responseTemplates = mapTemplateValues(integrationResponeConfig['responseTemplates'])
    apig.put_integration_response(
        restApiId=RESTAPI_CONFIG['id'],
        resourceId=resource_id,
        httpMethod=ENDPOINT_CONFIG['method'],
        statusCode=integrationResponeConfig['statusCode'],
        selectionPattern=integrationResponeConfig['selectionPattern'],
        responseParameters=integrationResponeConfig['responseParameters'],
        responseTemplates=responseTemplates,
    )
    print "--> put method integration response", integrationResponeConfig['selectionPattern']


apig.create_deployment(
    restApiId=RESTAPI_CONFIG['id'],
    stageName='head',
    description='Deployed from BAWS at {}'.format(str(datetime.datetime.now()))
)

print "--> created deployment"

print "All done, api Endpoint is https://{}.execute-api.eu-west-1.amazonaws.com/head{}".format(
    RESTAPI_CONFIG['id'],
    ENDPOINT_CONFIG['path'])
