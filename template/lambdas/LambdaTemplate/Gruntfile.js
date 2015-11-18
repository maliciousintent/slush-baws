

module.exports = function(grunt) {

  // Project configuration.
  grunt.initConfig({
    pkg: grunt.file.readJSON('package.json'),

    browserify: {
      dev: {
        files: {
          'lambda_function/index.js': ['./lambda_function.js'],
        },
        options: {
          watch: true,
          keepAlive:true,
          transform: [
            'babelify',
            'jadeify'
          ]
        },
      },

      dist: {
        files: {
          'lambda_function/index.js': ['./lambda_function.js'],
        },
        options: {
          watch: false,
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
