import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: 'Dashboard', component: () => import('@/pages/Dashboard.vue') },
  { path: '/list/:key', name: 'List', component: () => import('@/pages/DocList.vue') },
  { path: '/reports', name: 'Reports', component: () => import('@/pages/ReportsIndex.vue') },
  { path: '/report/:key', name: 'Report', component: () => import('@/pages/ReportView.vue') },
  // Target of the approval links sent by email / WhatsApp. Frappe enforces sign-in on
  // /kamil itself, and every action on the page re-checks roles server-side.
  {
    path: '/payment-approval/:name',
    name: 'PaymentApproval',
    component: () => import('@/pages/PaymentApproval.vue'),
  },
  { path: '/chart-of-accounts', name: 'ChartOfAccounts', component: () => import('@/pages/ChartOfAccounts.vue') },
  { path: '/users', name: 'Users', component: () => import('@/pages/Users.vue') },
  { path: '/settings/email', name: 'EmailSettings', component: () => import('@/pages/EmailSettings.vue') },
  { path: '/settings/payments', name: 'AppSettings', component: () => import('@/pages/AppSettings.vue') },
]

const router = createRouter({
  history: createWebHistory('/kamil'),
  routes,
})

export default router
