import type { NextConfig } from 'next';
import withPWAInit from '@ducanh2912/next-pwa';

const withPWA = withPWAInit({
  dest: 'public',
  disable: process.env.NODE_ENV === 'development',
});

const nextConfig: NextConfig = {
  // Silence Turbopack warning — next-pwa injects a webpack config that
  // Turbopack doesn't use in dev. Adding an empty turbopack key suppresses it.
  turbopack: {},
};

export default withPWA(nextConfig);
