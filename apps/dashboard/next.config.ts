import type { NextConfig } from "next";

const nextConfig = {
  output: "standalone",
  allowedDevOrigins: [
    "192.168.40.212",
    "192.168.40.248",
  ],
};

export default nextConfig;
