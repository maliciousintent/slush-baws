#!/bin/sh

source ./baws.env

STACK_NAME=${APP_NAME}-u${DEPLOYMENT_NAME}

aws cloudformation list-stack-resources --stack-name $STACK_NAME  # warning: silencing output here will cause the exit code to not be correct
STACK_EXISTS_CODE=$?

if [[ $STACK_EXISTS_CODE -eq 255 ]]; then
  echo "Creating NEW stack"
  CMD=create-stack
else
  CMD=update-stack
fi

echo -e "\nNotice: Starting User-Resources deploy, this may result in creation or deletion" \
    "of resources and might cause DATA LOSS in case of any bug or misconfiguration." \
    "Press a key to acknowledge and continue, CTRL-C to abort within 2 seconds.\n"
read -t2 -n1

UPDATED_RESOURCES=$(node <<EOF
var fs = require('fs');
var original = JSON.parse(fs.readFileSync('./resources/user-resources.json'));
var overrides = JSON.parse(fs.readFileSync('./resources/${DEPLOYMENT_NAME}/user-overrides.json'));

var lodash = require('lodash');
lodash.merge(original, overrides);

var jmespath = require('jmespath');
var jsonpath = require('jsonpath');
var sources = {
  api: JSON.parse(fs.readFileSync('./resources/api-dump.json')),
  'lambda-resources': JSON.parse(fs.readFileSync('./resources/lambda-resources-dump.json')),
  env: process.env
};

original._replacePaths.forEach(function (tuple) {
  if (tuple[0] === '_comment') return;

  console.error('Replacing', tuple);

  var found = jsonpath.apply(original, tuple[0], function (oldValue) {
    if (oldValue !== "") {
      console.error("Potential Bug: You are trying to replace a not-empty value (after merge) with a jmespath-evaluated item.");
      process.exit(1);
      return;
    }

    var newValue = jmespath.search(sources, tuple[1]);
    if (newValue == null) {
      throw new Error('Configuration error: new value from jmespath expression is null-ish. Expression = ' + tuple[1]);
    }
    return newValue;
  });

  if (found.length === 0) {
    throw new Error("Configuration error: no result for jsonpath expression = " + tuple[0]);
  }
});

delete original._replacePaths;

console.log(JSON.stringify(original, null, 2));
process.exit(0);

EOF
)


echo "Updating/creating stack $STACK_NAME"

aws cloudformation $CMD \
  --stack-name $STACK_NAME \
  --template-body "$UPDATED_RESOURCES" \
  --capabilities '["CAPABILITY_IAM"]'

echo -n "Please wait for Cloudformation stack update..."

STACK_STATUS=''
while [ "$STACK_STATUS" != "UPDATE_COMPLETE" ]; do
  sleep 10
  STACK_STATUS=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --output text --query 'Stacks[0].StackStatus')
  echo -n "."
done

echo -e "\nOk!"

echo "Dumping resources..."
aws cloudformation list-stack-resources --stack-name $STACK_NAME > ./resources/user-resources-dump.json
