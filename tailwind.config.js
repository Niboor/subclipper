/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./subclipper/app/templates/**/*.html",
    "./subclipper/app/static/**/*.js"
  ],
  theme: {
    extend: {
      colors: {
        'primary': '#1a1a1a',
        'secondary': '#4a4a4a',
      },
      spacing: {
        '1.5': '0.375rem',
        '2.5': '0.625rem',
      }
    },
  },
  plugins: [require("daisyui")],
  daisyui: {
    themes: ["light", "dark"],
    darkTheme: "dark",
  },
} 