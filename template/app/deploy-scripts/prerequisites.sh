#!/bin/sh
set -e

source ./baws.env

_UTIL_PIPE_REPLACE_QUOTES=

mkdir lambdas resources endpoints || true

aws s3api create-bucket \
        --region eu-west-1 \
        --bucket $SUPPORT_BUCKET_NAME \
        --create-bucket-configuration '{"LocationConstraint": "eu-west-1"}' || true


API_NAME=${APP_NAME}_${DEPLOYMENT_NAME}

API_ID=$(aws apigateway create-rest-api \
        --region eu-west-1 \
        --name "$API_NAME" \
        --query 'id')


API_ID=$(echo "$API_ID" | sed -e 's/^"//'  -e 's/"$//')
echo "REST ID $API_ID"

API_ROOT=$(aws apigateway get-resources --rest-api-id $API_ID --query 'items[0].id' | sed -e 's/^"//'  -e 's/"$//')
aws apigateway put-method \
  --rest-api-id "$API_ID" \
  --resource-id "$API_ROOT" \
  --http-method GET \
  --authorization-type NONE \
  --no-api-key-required \
  --request-parameters '{}'

aws apigateway put-method-response \
  --rest-api-id "$API_ID" \
  --resource-id "$API_ROOT" \
  --http-method "GET" \
  --status-code 301 \
  --response-models '{"application/json":"Empty"}' \
  --response-parameters '{"method.response.header.Location":true}'

aws apigateway put-integration \
  --rest-api-id "$API_ID" \
  --resource-id "$API_ROOT" \
  --http-method GET \
  --type MOCK \
  --request-templates '{"application/json":"{\"statusCode\": 301}"}'

aws apigateway put-integration-response \
  --rest-api-id "$API_ID" \
  --resource-id "$API_ROOT" \
  --http-method GET \
  --status-code 301 \
  --response-templates '{"application/json":"redirect"}' \
  --response-parameters "{\"method.response.header.Location\":\"'https://github.com/plasticpanda'\"}"

DEPLOYMENT_ID=$(aws apigateway create-deployment \
  --rest-api-id "$API_ID" \
  --description "first deployment created by baws" \
  --stage-name "head" \
  --stage-description "default stage created by baws" \
  --no-cache-cluster-enabled \
  --output text \
  --query 'id')

API_URL="https://$API_ID.execute-api.eu-west-1.amazonaws.com/head"
echo "Your API BASE URL is $API_URL"

ROLE_NAME="RoleForApigAWS_$API_NAME"

DEFAULT_APIG_ROLE_FOR_AWS=$(aws iam create-role --query "Role.Arn" --cli-input-json "{
    \"Path\": \"/\",
    \"RoleName\": \"$ROLE_NAME\",
    \"AssumeRolePolicyDocument\": \"{\\\"Version\\\":\\\"2012-10-17\\\",\\\"Statement\\\":[{\\\"Sid\\\":\\\"\\\",\\\"Effect\\\":\\\"Allow\\\",\\\"Principal\\\":{\\\"Service\\\":\\\"apigateway.amazonaws.com\\\"},\\\"Action\\\":\\\"sts:AssumeRole\\\"}]}\"
}")

echo "Created Role $DEFAULT_APIG_ROLE_FOR_AWS"

aws iam put-role-policy \
  --role-name $ROLE_NAME \
  --policy-name "allow-lambda-calls" \
  --policy-document '{"Version":"2012-10-17","Statement":[{"Sid":"Stmt1447776223000","Effect":"Allow","Action":["lambda:InvokeFunction"],"Resource":["*"]}]}'


mkdir -p ./resources/$DEPLOYMENT_NAME/
cat > ./resources/$DEPLOYMENT_NAME/api.json <<EOF
{
  "name": "$API_NAME",
  "id": "$API_ID",
  "url": "$API_URL",
  "apigRoleArn": $DEFAULT_APIG_ROLE_FOR_AWS
}
EOF
