/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["DM Sans", "system-ui", "sans-serif"],
      },
      colors: {
        surface: "#ffffff",
        muted: "#64748b",
        border: "#e2e8f0",
        bg: "#f4f6f8",
      },
    },
  },
  plugins: [],
};
