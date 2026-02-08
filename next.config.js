/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    serverComponentsExternalPackages: ["better-sqlite3"],
  },
  // Optimize for production
  poweredByHeader: false,
  reactStrictMode: true,
};

module.exports = nextConfig;
