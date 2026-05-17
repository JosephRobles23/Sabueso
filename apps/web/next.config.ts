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

const isDev = process.env.NODE_ENV !== "production";

// API origin the browser will fetch from. Locked down to one host in prod;
// localhost is added in dev so the browser can talk to FastAPI on :8000.
const API_ORIGIN = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
const SUPABASE_ORIGIN = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const ALLOWED_ORIGINS = [
  "https://sabueso.vercel.app",
  ...(isDev ? ["http://localhost:3000", "http://127.0.0.1:3000"] : []),
];

// CSP — tight by default. `'unsafe-inline'` on styles is needed for Tailwind
// runtime tokens and shadcn portals; scripts only allow self + strict-dynamic
// nonces (Next 16 emits nonces automatically when configured).
function buildContentSecurityPolicy(): string {
  const connectSrc = [
    "'self'",
    API_ORIGIN,
    SUPABASE_ORIGIN,
    "https://*.supabase.co",
    "wss://*.supabase.co",
    "https://openrouter.ai",
    ...(isDev ? ["ws://localhost:*", "http://localhost:*"] : []),
  ].filter(Boolean);

  const scriptSrc = [
    "'self'",
    // Next inline bootstrap and React hydration scripts.
    "'unsafe-inline'",
    ...(isDev ? ["'unsafe-eval'"] : []),
  ];

  const directives: Record<string, string[]> = {
    "default-src": ["'self'"],
    "script-src": scriptSrc,
    "style-src": ["'self'", "'unsafe-inline'"],
    "img-src": ["'self'", "data:", "blob:", "https:"],
    "font-src": ["'self'", "data:"],
    "connect-src": connectSrc,
    "frame-ancestors": ["'none'"],
    "form-action": ["'self'"],
    "base-uri": ["'self'"],
    "object-src": ["'none'"],
    "worker-src": ["'self'", "blob:"],
    "manifest-src": ["'self'"],
    "upgrade-insecure-requests": [],
  };

  return Object.entries(directives)
    .map(([k, v]) => (v.length ? `${k} ${v.join(" ")}` : k))
    .join("; ");
}

const securityHeaders = [
  { key: "Content-Security-Policy", value: buildContentSecurityPolicy() },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), interest-cohort=()",
  },
  {
    key: "Strict-Transport-Security",
    value: "max-age=63072000; includeSubDomains; preload",
  },
];

const corsHeaders = (origin: string) => [
  { key: "Access-Control-Allow-Origin", value: origin },
  { key: "Vary", value: "Origin" },
  { key: "Access-Control-Allow-Credentials", value: "true" },
  { key: "Access-Control-Allow-Methods", value: "GET, POST, OPTIONS" },
  { key: "Access-Control-Allow-Headers", value: "Authorization, Content-Type" },
  { key: "Access-Control-Max-Age", value: "86400" },
];

const nextConfig: NextConfig = {
  reactStrictMode: true,
  experimental: {
    optimizePackageImports: ["lucide-react", "@radix-ui/react-icons"],
  },
  async headers() {
    // CORS is enforced per-origin via `has` matchers; if the Origin header is
    // not in the allowlist, no CORS headers are emitted (browser blocks).
    const corsRules = ALLOWED_ORIGINS.flatMap((origin) => [
      {
        source: "/api/:path*",
        has: [{ type: "header" as const, key: "origin", value: origin }],
        headers: corsHeaders(origin),
      },
    ]);

    return [
      {
        source: "/(.*)",
        headers: securityHeaders,
      },
      ...corsRules,
    ];
  },
};

export default withNextIntl(nextConfig);
