/** @type {import('next').NextConfig} */

const nextConfig = {
  reactStrictMode: true,

  turbopack: {
    root: process.cwd()
  },

  // Every school has its own address - medicaps.localhost:3000 here
  // (lib/school.js). The dev server refuses its own scripts to any
  // host but localhost unless the school addresses are listed.
  allowedDevOrigins: ["*.localhost"]
};

export default nextConfig;
