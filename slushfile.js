
var gulp = require('gulp');
var install = require('gulp-install');
var conflict = require('gulp-conflict');
var template = require('gulp-template');
var inquirer = require('inquirer');


gulp.task('default', function (done) {

  inquirer.prompt([
    { type: 'list', name: 'type',
                    message: 'What to scaffold?',
                    choices: ['app', new inquirer.Separator('----'), 'lambda', 'endpoint', 'model'],
                    default: gulp.args[0] || 2,
    },
    { type: 'text', name: 'name',
                    message: 'Resource name (a-zA-Z0-9) =>',
                    validate: function (input) { return input.match(/[a-zA-Z][a-zA-Z0-9]+/) !== null; },
                    default: gulp.args[1],
    },
    { type: 'list', name: 'contentType',
                    message: 'Response Content-Type?',
                    choices: ['html', 'json'],
                    default: gulp.args[2],
                    when: function (answers) { return answers.type === 'endpoint' || answers.type === 'lambda'; },
    },
    { type: 'list', name: 'lambdaResponseType',
                    message: 'Jade or plain HTML?',
                    choices: ['jade', 'plain'],
                    default: gulp.args[3],
                    when: function (answers) { return answers.type === 'lambda'; },
    },
    { type: 'list', name: 'rest_method',
                    message: 'REST HTTP method =>',
                    choices: ['GET', 'PUT', 'POST', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD'],
                    default: gulp.args[4] || 'GET',
                    when: function (answers) { return answers.type === 'endpoint'; },
    },
    { type: 'list', name: 'enableCors',
                    message: 'Enable CORS?',
                    choices: ['yes', 'no'],
                    default: gulp.args[5] || 'yes',
                    when: function (answers) { return answers.type === 'endpoint'; },
    },
    { type: 'text', name: 'rest_path',
                    message: 'REST path =>',
                    default: gulp.args[6] || '/foo',
                    when: function (answers) { return answers.type === 'endpoint'; },
    },
    { type: 'confirm', name: 'moveon',
                       message: 'Confirm?',
    },
  ],

  function (answers) {
    if (!answers.moveon) {
      return done();
    }

    var RESOURCE_NAME = answers.name;

    var pipe = gulp;
    var sourceDirs = [];

    if (answers.type === 'app') {
      pipe = pipe.src([
        __dirname + '/template/app/**',
        __dirname + '/template/app/.gitignore',
      ])
      .pipe(template(answers, { interpolate: /{{([\s\S]+?)}}/g }))
      .pipe(conflict('./'))
      .pipe(gulp.dest('./')) // relative to cwd
      .pipe(install())

    } else if (answers.type === 'lambda') {
      var srcDirs = [
        __dirname + '/template/lambdas/LambdaTemplate/**',
        __dirname + '/template/lambdas/LambdaTemplate/.babelrc',
      ];

      if (answers.lambdaResponseType === 'jade') {
        srcDirs.push(__dirname + '/template/lambdas/LambdaTemplateWithJade/**');
      }

      pipe = pipe.src(srcDirs)
      .pipe(template(answers, { interpolate: /{{([\s\S]+?)}}/g }))
      .pipe(conflict('./lambdas/' + RESOURCE_NAME))
      .pipe(gulp.dest('./lambdas/' + RESOURCE_NAME)) // relative to cwd
      .pipe(install())

    } else if (answers.type === 'endpoint') {
      pipe = pipe.src([
        __dirname + '/template/endpoints/EndpointTemplate/**',
      ])
      .pipe(template(answers, { interpolate: /{{([\s\S]+?)}}/g }))
      .pipe(conflict('./endpoints/' + RESOURCE_NAME))
      .pipe(gulp.dest('./endpoints/' + RESOURCE_NAME)) // relative to cwd

    } else {
      throw new Error('Configuration error: unkown resource type `' + answers.type + '`');
    }

    pipe.on('end', function () {
      done();
    })
    .resume();

  });
});
