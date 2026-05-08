import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
  plugins: [svelte()],
  css: {
    postcss: './postcss.config.js',
  },
  server: {
    // During dev, proxy WebSocket and camera requests to the daemon
    proxy: {
      '/ws': {
        target: 'ws://localhost:8080',
        ws: true,
      },
      '/camera': {
        target: 'http://localhost:8080',
      },
    },
  },
});
