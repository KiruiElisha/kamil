import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: 'Dashboard', component: () => import('@/pages/Dashboard.vue') },
  { path: '/list/:key', name: 'List', component: () => import('@/pages/DocList.vue') },
  { path: '/reports', name: 'Reports', component: () => import('@/pages/ReportsIndex.vue') },
  { path: '/report/:key', name: 'Report', component: () => import('@/pages/ReportView.vue') },
]

const router = createRouter({
  history: createWebHistory('/kamil'),
  routes,
})

export default router
