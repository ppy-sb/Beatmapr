import { fileURLToPath, URL } from 'node:url'

export default defineNuxtConfig({
  compatibilityDate: '2025-10-06',
  app: {
    baseURL: '/',
  },
  modules: ['@pinia/nuxt'],
  css: ['~/assets/styles.css'],
  alias: {
    '@': fileURLToPath(new URL('./src', import.meta.url)),
  },
})
