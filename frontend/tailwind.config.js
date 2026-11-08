/** @type {import('tailwindcss').Config} */
const c = (name) => `rgb(var(--${name}) / <alpha-value>)`;
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "media",
  theme: {
    extend: {
      colors: {
        bg: c("bg"),
        panel: c("panel"),
        line: c("line"),
        ink: c("ink"),
        mute: c("mute"),
        accent: c("accent"),
        warn: c("warn"),
        bad: c("bad"),
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};
