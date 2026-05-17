import path from "node:path";
import { loadEnvConfig } from "@next/env";
import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

// Sabueso is a pnpm monorepo; the canonical .env lives at the repo root.
// Next only loads env files from the app directory, so we manually pull the
// repo-root files (.env, .env.local, .env.development) before the config is
// evaluated. This makes NEXT_PUBLIC_* vars available to both the dev server
// and the client bundle.
loadEnvConfig(path.resolve(__dirname, "../.."), process.env.NODE_ENV !== "production");

const withNextIntl = createNextIntlPlugin("./i18n.ts");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  experimental: {
    optimizePackageImports: ["lucide-react", "@radix-ui/react-icons"],
  },
};

export default withNextIntl(nextConfig);
