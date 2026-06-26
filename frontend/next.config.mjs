/** @type {import('next').NextConfig} */
const BACKEND = process.env.BACKEND_URL || "http://localhost:8000";

const nextConfig = {
  // Proxy /api/* to the FastAPI backend so the browser stays same-origin (no CORS).
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND}/:path*` }];
  },
};

export default nextConfig;
