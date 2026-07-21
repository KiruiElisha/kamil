import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: 'Dashboard', component: () => import('@/pages/Dashboard.vue') },
  { path: '/list/:key', name: 'List', component: () => import('@/pages/DocList.vue') },
]

const router = createRouter({
  history: createWebHistory('/kamil'),
  routes,
})

export default router
