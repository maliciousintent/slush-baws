#!/bin/env python2.7

import sys
import os
import time
import datetime
import json
from subprocess import call

import boto3
apig = boto3.client('apigateway')


if not len(sys.argv) == 2 or not sys.argv[1]:
    raise Exception("First parameter should be a ENDPOINT name")


""" Setup """

MODEL_NAME = sys.argv[1]
MODEL_DIR = os.path.join(".", "endpoints", "models")
MODEL_CONTENT = open(os.path.join(MODEL_DIR, "".join([MODEL_NAME, ".json"]))).read()

RESTAPI_CONFIG = json.load(open(os.path.join(".", "resources", "default-deployment", "api.json")))

print "Deploying model", MODEL_NAME

try:
    print "--> finding model", MODEL_NAME
    apig.get_model(restApiId=RESTAPI_CONFIG['id'],
                   modelName=MODEL_NAME)
    create = False

except Exception, e:
    print "----> model did not exist"
    create = True


if create:
    apig.create_model(restApiId=RESTAPI_CONFIG['id'],
                      name=MODEL_NAME,
                      schema=MODEL_CONTENT,
                      contentType='application/json'
                      )
    print "--> created model", MODEL_NAME

else:
    apig.update_model(restApiId=RESTAPI_CONFIG['id'],
                      modelName=MODEL_NAME,
                      patchOperations=[{
                        "op": "replace",
                        "path": "/schema",
                        "value": MODEL_CONTENT
                      }])
    print "--> updated model", MODEL_NAME

print "All done!"
