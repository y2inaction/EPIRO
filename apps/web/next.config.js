/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    unoptimized: true,
  },
  // There is deliberately no `env` block. Anything listed there is inlined
  // into the bundle at build time, which is how the API address came to be
  // frozen into the image: a built container could not be pointed at a
  // different environment without rebuilding it. The portal reads API_URL at
  // request time instead — see lib/api.ts.

  // Promoted out of experimental in Next 15. swcMinify was removed entirely:
  // minification is always on.
  typedRoutes: true,
}

module.exports = nextConfig
