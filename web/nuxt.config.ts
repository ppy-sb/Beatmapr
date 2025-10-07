import { fileURLToPath, URL } from 'node:url'

export default defineNuxtConfig({
  compatibilityDate: '2025-10-06',
  app: {
    baseURL: '/',
    head: {
      meta: [
        {
          name: 'description',
          content:
            'Fetch your relax scores from Akatsuki and match them against official bancho beatmap packs. Visualize your progress toward full pack completion, discover which maps are missing, and track leaderboard metadata.',
        },
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
        { name: 'theme-color', content: '#071028' },
        { name: 'apple-mobile-web-app-capable', content: 'yes' },
        { name: 'apple-mobile-web-app-status-bar-style', content: 'black-translucent' },
      ],
    }
  },
  modules: ['@pinia/nuxt'],
  css: ['~/assets/styles.css'],
})
