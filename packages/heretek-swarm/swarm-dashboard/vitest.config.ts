/// <reference types="vitest" />
/// <reference types="jest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: [
      'src/**/*.{test,spec}.{ts,tsx}',
      'tests/components/**/*.{test,spec}.{ts,tsx}',
      'tests/stores/**/*.{test,spec}.{ts,tsx}',
      'tests/hooks/**/*.{test,spec}.{ts,tsx}',
    ],
    coverage: {
      reporter: ['text', 'json', 'html'],
    },
    // Force React into test mode so act() works
    env: {
      NODE_ENV: 'test',
    },
  },
});
