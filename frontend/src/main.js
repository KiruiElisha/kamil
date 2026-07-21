import './index.css'
import { createApp } from 'vue'
import { setConfig, frappeRequest } from 'frappe-ui'
import App from './App.vue'
import router from './router'

setConfig('resourceFetcher', frappeRequest)

const app = createApp(App)
app.use(router)
app.mount('#app')

// PWA service worker (asset caching + installability)
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/kamil-sw.js', { scope: '/' }).catch(() => {})
  })
}
