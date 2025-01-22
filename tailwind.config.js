/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.html', // Adjust the path to your Flask templates
    './static/**/*.js', // If you have custom JS files
  ],
  theme: {
    extend: {},
  },
  plugins: [],
};

