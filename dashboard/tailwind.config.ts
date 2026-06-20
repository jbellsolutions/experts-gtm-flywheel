import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0a0a0a",
        accent: "#2563eb",
        warn: "#f59e0b",
        ok: "#10b981",
        bad: "#ef4444",
      },
    },
  },
  plugins: [],
};
export default config;
