/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  base: '/ai_avatar/',
  plugins: [react()],
  publicDir: '../../AI_Avatar/public',
  resolve: {
    alias: {
      react: new URL('./node_modules/react', import.meta.url).pathname,
      'react-dom': new URL('./node_modules/react-dom', import.meta.url).pathname,
    },
  },
  build: {
    outDir: '../../web/ai_avatar',
    emptyOutDir: true,
    rollupOptions: {
      input: 'avatar.html',
    },
  },
  test: { environment: 'jsdom', setupFiles: './src/testSetup.ts' },
});
