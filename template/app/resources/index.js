import { search } from 'jmespath';

import RESOURCES_API from './api-dump.json';
import RESOURCES_LAMBDA from './lambda-resources-dump.json';
import RESOURCES_USER from './user-resources-dump.json';

export default function load(sourceName, jmesPathExpression) {
  let sourceObject;

  switch (sourceName) {
  case 'api':
    sourceObject = RESOURCES_API;
    break;
  case 'lambda':
    sourceObject = RESOURCES_LAMBDA;
    break;
  case 'user':
    sourceObject = RESOURCES_USER;
    break;
  default:
    throw new Error('Invalid source in resource loader, must be one of: api, lambda, user');
  }

  return search(sourceObject, jmesPathExpression);
}
