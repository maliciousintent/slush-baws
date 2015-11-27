#!/bin/env python2.7

import sys
import os
import time
import datetime
import json
from copy import deepcopy
from subprocess import call

import boto3
s3 = boto3.resource("s3")
cf = boto3.client('cloudformation')
apig = boto3.client('apigateway')


""" Configuration from baws.env """
SUPPORT_BUCKET_NAME = os.getenv("SUPPORT_BUCKET_NAME")
APP_NAME = os.getenv("APP_NAME")
DEPLOYMENT_NAME = os.getenv("DEPLOYMENT_NAME")


if not os.getenv("BAWS_SOURCED"):
    raise Exception("Please source baws.env before running this script.")


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
    open(os.path.join(".", "resources", DEPLOYMENT_NAME, "api.json")),
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


def deployMethod(ENDPOINT_CONFIG_PARAM):
    try:
        print "--> deleting method", ENDPOINT_CONFIG_PARAM['method']
        apig.delete_method(
            restApiId=RESTAPI_CONFIG['id'],
            resourceId=resource_id,
            httpMethod=ENDPOINT_CONFIG_PARAM['method']
        )

    except Exception, e:
        print "----> method did not exist"

    apig.put_method(
        restApiId=RESTAPI_CONFIG['id'],
        resourceId=resource_id,
        httpMethod=ENDPOINT_CONFIG_PARAM['method'],
        authorizationType='NONE',
        apiKeyRequired=False,
        requestParameters=ENDPOINT_CONFIG_PARAM['requestParameters'],
        requestModels=ENDPOINT_CONFIG_PARAM['requestModels']
    )
    print "--> put method", ENDPOINT_CONFIG_PARAM['method']

    for methodResponseKey, methodResponseConfig in ENDPOINT_CONFIG_PARAM['methodResponses'].iteritems():
        apig.put_method_response(
            restApiId=RESTAPI_CONFIG['id'],
            resourceId=resource_id,
            httpMethod=ENDPOINT_CONFIG_PARAM['method'],
            statusCode=methodResponseConfig['statusCode'],
            responseParameters=methodResponseConfig['responseParameters'],
            responseModels=methodResponseConfig['responseModels'],
        )
        print "--> put method response", methodResponseConfig['statusCode']

    # prepare put_integration parameters
    requestTemplates = mapTemplateValues(ENDPOINT_CONFIG_PARAM['methodIntegration']['requestTemplates'])

    if ENDPOINT_CONFIG_PARAM['methodIntegration']['type'] == "Lambda":
        RESOURCES_FILE_NAME = os.path.join('.', 'resources', 'lambda-resources-dump.json')
        LAMBDAS_DESCRIPTORS = json.load(open(RESOURCES_FILE_NAME))

        try:
            myLambdaArn = filter(lambda fn: fn["LogicalResourceId"] == ENDPOINT_CONFIG_PARAM['methodIntegration']['uri'],
                                 LAMBDAS_DESCRIPTORS)[0]["FunctionArn"]

            ENDPOINT_CONFIG_PARAM['methodIntegration']['credentials'] = RESTAPI_CONFIG['apigRoleArn']
            ENDPOINT_CONFIG_PARAM['methodIntegration']['type'] = 'AWS'
            ENDPOINT_CONFIG_PARAM['methodIntegration']['httpMethod'] = 'POST'
            ENDPOINT_CONFIG_PARAM['methodIntegration']['uri'] = "/".join([
                "arn:aws:apigateway:eu-west-1:lambda:path", "2015-03-31", "functions",
                myLambdaArn,
                "invocations"
            ])

        except Exception, e:
            print "Cannot find lambda with LogicalID", ENDPOINT_CONFIG_PARAM['methodIntegration']['uri']
            print "Make sure you prepended `Fn` to the uri in the config.json file of your endpoint."
            print "Please inspect your resources from the AWS CF console."
            raise e

    apig.put_integration(
        restApiId=RESTAPI_CONFIG['id'],
        resourceId=resource_id,
        httpMethod=ENDPOINT_CONFIG_PARAM['method'],
        type=ENDPOINT_CONFIG_PARAM['methodIntegration']['type'],
        credentials=ENDPOINT_CONFIG_PARAM['methodIntegration']['credentials'],  # required for AWS integrations
        integrationHttpMethod=ENDPOINT_CONFIG_PARAM['methodIntegration']['httpMethod'],
        uri=ENDPOINT_CONFIG_PARAM['methodIntegration']['uri'],
        requestParameters=ENDPOINT_CONFIG_PARAM['methodIntegration']['requestParameters'],
        requestTemplates=requestTemplates,
    )
    print "--> put method integration with type =", ENDPOINT_CONFIG_PARAM['methodIntegration']['type']

    for integrationResponseKey, integrationResponeConfig in ENDPOINT_CONFIG_PARAM['methodIntegration']['integrationResponses'].iteritems():
        responseTemplates = mapTemplateValues(integrationResponeConfig['responseTemplates'])
        apig.put_integration_response(
            restApiId=RESTAPI_CONFIG['id'],
            resourceId=resource_id,
            httpMethod=ENDPOINT_CONFIG_PARAM['method'],
            statusCode=integrationResponeConfig['statusCode'],
            selectionPattern=integrationResponeConfig['selectionPattern'],
            responseParameters=integrationResponeConfig['responseParameters'],
            responseTemplates=responseTemplates,
        )
        print "--> put method integration response", integrationResponeConfig['selectionPattern']

deployMethod(ENDPOINT_CONFIG)

if ENDPOINT_CONFIG["_bawsEnableCors"] == True:
    CORS_CONFIG = deepcopy(ENDPOINT_CONFIG)

    CORS_CONFIG['method'] = 'OPTIONS'
    CORS_CONFIG['requestParameters'] = {}
    CORS_CONFIG['requestModels'] = {}

    CORS_CONFIG['methodIntegration']['type'] = 'MOCK'
    CORS_CONFIG['methodIntegration']['requestParameters'] = {}
    # CORS_CONFIG['methodIntegration']['credentials']  # InternalFailure
    CORS_CONFIG['methodIntegration']['httpMethod'] = ''
    CORS_CONFIG['methodIntegration']['uri'] = ''

    deployMethod(CORS_CONFIG)


apig.create_deployment(
    restApiId=RESTAPI_CONFIG['id'],
    stageName='head',
    description='Deployed from BAWS at {}'.format(str(datetime.datetime.now()))
)

print "--> created deployment"

print "All done, api Endpoint is https://{}.execute-api.eu-west-1.amazonaws.com/head{}".format(
    RESTAPI_CONFIG['id'],
    ENDPOINT_CONFIG['path'])
