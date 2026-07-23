/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  base: '/tts_clone_test/',
  plugins: [react()],
  build: {
    outDir: '../../web/tts_clone_test',
    emptyOutDir: true,
    rollupOptions: {
      input: 'tts-clone.html',
    },
  },
  test: { environment: 'jsdom', setupFiles: './src/testSetup.ts' },
});
