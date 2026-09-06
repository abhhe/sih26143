/**
 * Application API configuration.
 * Configurable via Vite/Vercel environment variables:
 * - VITE_API_BASE_URL (e.g. 'https://api.yourdomain.com' or 'http://localhost:8000')
 * - VITE_API_URL (fallback alias)
 * Defaults to 'http://localhost:8000' for local development.
 */
const rawBaseUrl =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ||
  (import.meta.env.VITE_API_URL as string | undefined) ||
  'http://localhost:8000';

export const API_BASE_URL: string = rawBaseUrl.replace(/\/+$/, '');
