#!/bin/bash
set -e

source ./baws.env

# Copy resources descriptors
cp ./resources/$DEPLOYMENT_NAME/api.json ./resources/api-dump.json || true


if [ "$1" == "--help" -o "$1" == "-h" -o "$1" == "help" ]; then

  echo -e "\nUsage: $0 <type> [<name>]"
  echo -e "* <type> can be one of: [l]ambda/[e]ndpoint/[le]lambda+endpoint/[m]odels/[u]ser."
  echo -e "* <name> is the folder name of the object to deploy. Requred for all types except 'user'."
  echo -e "\n\t- or -\n"
  echo -e "Usage: $0 <action> [<param>]"
  echo -e "* Possible values of <action>:"
  echo -e "\t* use: switch to (possibly new) deployment stage, <param> must be the stage name."
  echo -e "\t* setup: configure the current deployment stage and create initial resources."

  exit 255
fi

if [ -z "$1" ]; then
  echo "Missing parameter. Check $0 --help for usage."
  exit 255
fi

PYTHON="python2.7"
BASH="bash"


## FUNCTIONS

deploy_lambda () {
  echo "Beginning Lambda Deploy: $1"
  CWD=$(pwd)/.. $PYTHON deploy-scripts/lambda.py $1
}


deploy_endpoint () {
  echo "Beginning Endpoint Deploy: $1"
  CWD=$(pwd)/.. $PYTHON deploy-scripts/endpoint.py $1
}


deploy_model () {
  echo "Beginning Model Deploy: $1"
  CWD=$(pwd)/.. $PYTHON deploy-scripts/models.py $1
}


deploy_user () {
  echo "Beginning User-Resources Deploy"
  CWD=$(pwd)/.. $BASH deploy-scripts/user.sh
}


switch_stage () {
  sed -i "s/export DEPLOYMENT_NAME=.*/export DEPLOYMENT_NAME=$1/g" ./baws.env

  if [ -d ./resources/$DEPLOYMENT_NAME ]; then
    echo "Stage is new. Creating directories..."
    mkdir -p ./resources/$DEPLOYMENT_NAME
    echo '{}' >> ./resources/$DEPLOYMENT_NAME/user-overrides.json
    echo "Done. You should run 'b setup' now!"
  fi
}

setup () {
  CWD=$(pwd)/.. $BASH deploy-scripts/prerequisites.sh
}


## PROGRAM

TYPE=$1
OBJECT_NAME=$2

banner () {
  echo -e "App '$APP_NAME', deploying resource(s) to stage '$DEPLOYMENT_NAME'."
  echo "Press a key to continue, CTRL-C within 2 seconds to abort."
  read -n1 -t 2 || true
}


case $TYPE in

  l)
  banner
  deploy_lambda $OBJECT_NAME
  ;;

  e)
  banner
  echo -e "\nNotice: if you did update your Lambda function you may have to deploy it before" \
      "deploying its endpoint. This is needed because we search for Lambda ARNs when" \
      "parsing endpoint's config.json. You may want to run '$0 le $OBJECT_NAME' instead.\n"
  deploy_endpoint $OBJECT_NAME
  ;;

  le)
  banner
  deploy_lambda $OBJECT_NAME
  deploy_endpoint $OBJECT_NAME  # endpoint is faster, deploy first
  ;;

  m)
  banner
  deploy_model $OBJECT_NAME
  ;;

  u)
  banner
  deploy_user
  ;;

  use)
  switch_stage $OBJECT_NAME
  echo "Switched to deployment stage $OBJECT_NAME."
  ;;

  setup)
  banner
  setup
  ;;

esac
