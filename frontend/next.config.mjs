/** @type {import('next').NextConfig} */
const nextConfig = {
  // The repo root also has a package.json/lockfile (for `concurrently`), so pin
  // the tracing root to this app to silence Next's workspace-root inference.
  outputFileTracingRoot: import.meta.dirname,
};

export default nextConfig;
