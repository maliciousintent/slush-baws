#!/bin/bash
set -e

EXEC_DIR=$(pwd)
cd "$(dirname "$(realpath "$0")")/..";

source ./baws.env
source deploy-scripts/_print_utils.sh

echo "" > baws-debug.log


# Copy resources descriptors
cp ./resources/$DEPLOYMENT_NAME/api.json ./resources/api-dump.json || true


if [ "$1" == "--help" -o "$1" == "-h" -o "$1" == "help" ]; then

  echo -e "\nUsage: $0 <type> [<name>]"
  echo -e "* <type> can be one of: [l]ambda/[e]ndpoint/[le]lambda+endpoint/[m]odels/[u]ser/[all]."
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

test_lambda () {
  if [ -z "$1" ]; then
    LAMBDA_NAME=$(basename $EXEC_DIR)
  else
    LAMBDA_NAME=$1
  fi
  echo "You should install dependencies if needed."
  (cd lambdas/$LAMBDA_NAME && grunt dist && npm run dev)
}


deploy_lambda () {
  if [ -z "$1" ]; then
    LAMBDA_NAME=$(basename $EXEC_DIR)
  else
    LAMBDA_NAME=$1
  fi

  echo "Beginning Lambda Deploy: $LAMBDA_NAME"
  CWD=$(pwd)/.. $PYTHON deploy-scripts/lambda.py $LAMBDA_NAME
}


deploy_endpoint () {
  if [ -z "$1" ]; then
    ENDPOINT_NAME=$(basename $EXEC_DIR)
  else
    ENDPOINT_NAME=$1
  fi

  echo "Beginning Endpoint Deploy: $ENDPOINT_NAME"
  CWD=$(pwd)/.. $PYTHON deploy-scripts/endpoint.py $ENDPOINT_NAME
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


lambda_npminstall_all () {
  h1 "Installing npm dependencies for each lambda..."
  LAMBDA_DIRS=$(cd lambdas && ls)
  for lam in $LAMBDA_DIRS; do
    if [ -d "lambdas/$lam" ]; then
      h2 "\n\t--> $lam"
      (cd lambdas/$lam && npm install) >> baws-debug.log
    fi
  done
  pOK "OK :-)"
}

lambda_build_all () {
  h1 "Building lambdas..."
  LAMBDA_DIRS=$(cd lambdas && ls)
  for lam in $LAMBDA_DIRS; do
    if [ -d "lambdas/$lam" ]; then
      h2 "\n\t--> $lam"
      (cd lambdas/$lam && grunt dist) >> baws-debug.log
    fi
  done
  pOK "OK :-)"
}


lambda_test_all () {
  h1 "Testing lambdas..."
  LAMBDA_DIRS=$(cd lambdas && ls)
  for lam in $LAMBDA_DIRS; do
    if [ -d "lambdas/$lam" ]; then
      h2 "\n\t--> $lam"
      (cd lambdas/$lam && npm run dev) >> baws-debug.log
    fi
  done
  pOK "OK :-)"
}


lambda_deploy_all () {
  h1 "Deploying lambdas..."
  LAMBDA_DIRS=$(cd lambdas && ls)
  for lam in $LAMBDA_DIRS; do
    if [ -d "lambdas/$lam" ]; then
      h2 "\n\t--> $lam"
      deploy_lambda $lam
    fi
  done
  pOK "OK :-)"
  pOK "Done with lambdas"
}


endpoint_deploy_all() {
  h2 "Deploy script for Endpoints"

  MODEL_DIRS=$(cd endpoints/models && ls)
  for model in $MODEL_DIRS; do
    if [ -d "endpoints/models/$model" ]; then
      h2 "\nDeploy script for model «$model»"
      deploy_model $model
      pOK "OK :-)"
    fi
  done
  h1 "Done with models"


  ENDPOINT_DIRS=$(cd endpoints && ls)
  for endp in $ENDPOINT_DIRS; do
    if [ -d "endpoints/$endp" -a "$endp" != "models" -a "$endp" != "templates" ]; then
      h2 "\nDeploy script for endpoint «$endp»"
      deploy_endpoint $endp
      pOK "OK :-)"
    fi
  done
  h1 "Done with endpoints"
}


deploy_all () {
  # @NOTICE: deploy order matters!
  BANNER_WAIT=false
  echo ""

  h1 "Deploy script for User Resources"
  deploy_user
  pOK "OK :-)"

  lambda_npminstall_all
  lambda_build_all
  lambda_test_all
  lambda_deploy_all

  endpoint_deploy_all

  pOK "Lambdas, Endpoints, Models, User-Resources have all been deployed to stage '$DEPLOYMENT_NAME'."
}


## PROGRAM

TYPE=$1
OBJECT_NAME=$2
BANNER_WAIT=true

banner () {
  echo -e "$CYAN"
  echo -e "__________    _____  __      __  _________ "
  echo -e "\______   \  /  _  \/  \    /  \/   _____/   "
  echo -e " |    |  _/ /  /_\  \   \/\/   /\_____  \    "
  echo -e " |    |   \/    |    \        / /        \   "
  echo -e " |______  /\____|__  /\__/\  / /_______  /   "
  echo -e "        \/         \/      \/          \/    "
  echo -e "$RESET"

  h1 "App '$APP_NAME', on stage '$DEPLOYMENT_NAME'."

  if [ $BANNER_WAIT == true ]; then
    pWARN "This script will deploy resource(s)."
    pWARN "Press a key to continue, CTRL-C within 2 seconds to abort."
    read -n1 -t 2 || true
  fi
}


case $TYPE in

  all)
  banner
  deploy_all
  ;;

  l)
  banner
  deploy_lambda $OBJECT_NAME
  ;;

  lt)
  BANNER_WAIT=false
  banner
  test_lambda $OBJECT_NAME
  ;;

  lia)
  BANNER_WAIT=false
  banner
  lambda_npminstall_all
  ;;

  lba)
  BANNER_WAIT=false
  banner
  lambda_build_all
  ;;

  lta)
  BANNER_WAIT=false
  banner
  lambda_test_all
  ;;

  ea)
  banner
  endpoint_deploy_all
  ;;

  e)
  banner
  pINFO "\nNotice: if you did update your Lambda function you may have to deploy it before" \
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
  banner
  switch_stage $OBJECT_NAME
  echo "Switched to deployment stage $OBJECT_NAME."
  ;;

  setup)
  banner
  setup
  ;;

esac

pOK "Be happy! :-)"
