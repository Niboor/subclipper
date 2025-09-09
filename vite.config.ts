import { resolve } from "path";
import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'
import {fileURLToPath, URL} from 'node:url';
export default defineConfig({
  build: {
    lib: {
      entry: resolve(__dirname, "subclipper/scripts/main.ts"),
      name: "subclipper",
      fileName: "main",
    },
    outDir: `subclipper/app/static/dist`,
  },
  plugins: [
    tailwindcss(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
})