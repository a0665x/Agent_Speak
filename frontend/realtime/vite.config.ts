/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  base: '/asr_realtime/',
  plugins: [react()],
  build: { outDir: '../../web/asr_realtime', emptyOutDir: true },
  test: { environment: 'jsdom', setupFiles: './src/testSetup.ts' }
});
