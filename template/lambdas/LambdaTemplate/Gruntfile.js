

module.exports = function(grunt) {

  // Project configuration.
  grunt.initConfig({
    pkg: grunt.file.readJSON('package.json'),

    browserify: {
      dev: {
        files: {
          'build/lambda_function.js': ['./lambda_function.js'],
        },
        options: {
          watch: true,
          keepAlive: true,
          browserifyOptions: {
            standalone: 'module',
          },
          transform: [
            'babelify',
            'jadeify'
          ]
        },
      },

      dist: {
        files: {
          'build/lambda_function.js': ['./lambda_function.js'],
        },
        options: {
          watch: false,
          keepAlive: false,
          browserifyOptions: {
            standalone: 'module',
          },
          transform: [
            'babelify',
            'jadeify'
          ]
        },
      }
    }
  });

  grunt.loadNpmTasks('grunt-browserify');
  // grunt.loadNpmTasks('grunt-contrib-watch');
  grunt.registerTask('default', ['browserify:dev']);
  grunt.registerTask('dist', ['browserify:dist']);

};
