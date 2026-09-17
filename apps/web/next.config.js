/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    unoptimized: true,
  },
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  },
  // Promoted out of experimental in Next 15. swcMinify was removed entirely:
  // minification is always on.
  typedRoutes: true,
}

module.exports = nextConfig
