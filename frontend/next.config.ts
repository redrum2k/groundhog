import type { NextConfig } from "next";

const backend = (process.env.BACKEND_URL ?? "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);
const config: NextConfig = {
  agentRules: false,
  devIndicators: false,
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/jobflow/:path*",
        destination: `${backend}/api/jobflow/:path*`,
      },
      {
        source: "/api/broker/:path*",
        destination: `${backend}/api/broker/:path*`,
      },
      {
        source: "/api/improvements/:path*",
        destination: `${backend}/api/improvements/:path*`,
      },
    ];
  },
};
export default config;
