import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Brand logos in the dashboard come from the favicon service.
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "www.google.com", pathname: "/s2/favicons/**" },
    ],
  },
};

export default nextConfig;
