import type { NextConfig } from "next";

// Local-dev convenience: proxy /api/* to the FastAPI backend (uvicorn
// default port) so `npm run dev` + a locally running backend work
// together with no CORS setup. Production Vercel routing between the
// Next.js and FastAPI Services is T060's concern (tasks.md Phase 6) and
// may supersede this.
const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
