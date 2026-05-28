/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./ui/templates/**/*.html", "./ui/partials/**/*.html"],
  theme: { extend: {} },
  plugins: [require("daisyui")],
  daisyui: { themes: ["dark"] },
};
