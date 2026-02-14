import { readFileSync } from 'fs';

// Read version from VERSION file (auto-bumped by CI on every push)
let appVersion = '?.?.?';
try {
  appVersion = readFileSync('./VERSION', 'utf-8').trim();
} catch {
  // Fallback to package.json version
  try {
    const pkg = JSON.parse(readFileSync('./package.json', 'utf-8'));
    appVersion = pkg.version;
  } catch { /* keep default */ }
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  env: {
    APP_VERSION: appVersion,
  },
};

export default nextConfig;
