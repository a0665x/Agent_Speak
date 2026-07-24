/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  base: '/asr_realtime/',
  plugins: [react()],
  resolve: {
    alias: {
      react: new URL('./node_modules/react', import.meta.url).pathname,
      'react-dom': new URL('./node_modules/react-dom', import.meta.url).pathname,
    },
  },
  build: { outDir: '../../web/asr_realtime', emptyOutDir: true },
  test: { environment: 'jsdom', setupFiles: './src/testSetup.ts' }
});
