/** @type {import('next').NextConfig} */

const nextConfig = {
  reactStrictMode: true,

  // A second dev server (e.g. one trying path addresses, lib/address.js)
  // needs its own build folder - two servers on one .next clash.
  distDir: process.env.NEXT_DIST_DIR || ".next",

  turbopack: {
    root: process.cwd()
  },

  // Every school has its own address - medicaps.localhost:3000 here
  // (lib/school.js). The dev server refuses its own scripts to any
  // host but localhost unless the school addresses are listed.
  allowedDevOrigins: ["*.localhost"]
};

export default nextConfig;
