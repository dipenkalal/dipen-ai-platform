import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  allowedDevOrigins: [
    "192.168.40.212",
    "192.168.40.248",
  ],
  async headers() {
    return [
      {
        source: "/guardian/:path*",
        headers: [
          {
            key: "Cache-Control",
            value: "no-store",
          },
          {
            key: "Permissions-Policy",
            value: (
              "microphone=(self), " +
              "on-device-speech-recognition=(self)"
            ),
          },
          {
            key: "Referrer-Policy",
            value: "same-origin",
          },
          {
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
