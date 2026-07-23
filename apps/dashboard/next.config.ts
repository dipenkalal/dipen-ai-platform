import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: [
    "192.168.40.248",
    "192.168.40.248:3000",
  ],
};

export default nextConfig;