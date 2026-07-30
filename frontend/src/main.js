import './index.css'
import { createApp } from 'vue'
import { setConfig, frappeRequest } from 'frappe-ui'
import App from './App.vue'
import router from './router'
import { getDefaults } from './data/defaults.js'

setConfig('resourceFetcher', frappeRequest)

const app = createApp(App)
app.use(router)
app.mount('#app')

// Fetched up front so the company's currency is known before the first amount is
// drawn — otherwise a list would render its totals unlabelled for a moment.
getDefaults()

// PWA service worker (asset caching + installability)
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/kamil-sw.js', { scope: '/' }).catch(() => {})
  })
}
