
// local runner for nodejs lambdas
// feel free to customize according to your needs

var fs = require('fs');

var context = {
  done: function (err, result) {
    if (err) {
      context.fail(err);
    } else {
      context.succeed(result);
    }
  },
  succeed: function (result) {
    console.log('Lambda function completed succesfully!');
    console.log(result);
  },
  fail: function (e) {
    console.error('Lambda execution terminated with error');
    throw e;
  },
  // @TODO: env ...
};

var event = JSON.parse(fs.readFileSync(__dirname + '/event.json'));

var module = require('../build/lambda_function.js');
module.lambda_handler(event, context);
