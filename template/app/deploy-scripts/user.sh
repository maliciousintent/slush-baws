#!/bin/sh

source ./baws.env

STACK_NAME=${APP_NAME}-u${DEPLOYMENT_NAME}

aws cloudformation list-stack-resources --stack-name $STACK_NAME 2&> /dev/null
STACK_EXISTS_CODE=$?

if [[ $STACK_EXISTS_CODE -eq 255 ]]; then
  CMD=create-stack
else
  CMD=update-stack
fi

echo -e "\nNotice: Starting User-Resources deploy, this may result in creation or deletion" \
    "of resources and might cause DATA LOSS in case of any bug or misconfiguration." \
    "Press a key to acknowledge and continue, CTRL-C to abort.\n"

UPDATED_RESOURCES=$(cat | node <<EOF
var fs = require('fs');
var original = JSON.parse(fs.readFileSync('./resources/user-resources.json'));
var overrides = JSON.parse(fs.readFileSync('./resources/${DEPLOYMENT_NAME}/user-overrides.json'));

var lodash = require('lodash');
lodash.merge(original, overrides);
console.log(JSON.stringify(original, null, 2));
process.exit(0);

EOF
)

echo $UPDATED_RESOURCES > ./resources/~user-resources.json

echo "Updating/creating stack $STACK_NAME"

aws cloudformation $CMD \
  --stack-name $STACK_NAME \
  --template-body "$UPDATED_RESOURCES" \
  --capabilities '["CAPABILITY_IAM"]'

echo "Done, you should wait for cloudformation to complete the update."
