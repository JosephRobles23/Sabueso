import type { Config } from "tailwindcss";

// Tailwind v4 is configured primarily via `@theme` blocks in app/globals.css.
// This file exists only for editor tooling that still expects a config file.
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./hooks/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
    "../../packages/ui/src/**/*.{ts,tsx}",
  ],
};

export default config;
