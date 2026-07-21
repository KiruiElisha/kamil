<template>
  <div class="flex h-screen w-screen overflow-hidden bg-surface-white">
    <Sidebar :header="header" :sections="sections" />

    <div class="flex min-w-0 flex-1 flex-col overflow-hidden">
      <header class="flex h-12 shrink-0 items-center justify-between border-b border-outline-gray-1 px-5">
        <span class="text-base font-semibold text-ink-gray-8">{{ pageTitle }}</span>
        <Dropdown :options="createOptions">
          <Button variant="solid" label="Create">
            <template #prefix><Plus class="h-4 w-4" /></template>
          </Button>
        </Dropdown>
      </header>
      <div class="flex-1 overflow-auto bg-surface-gray-1 p-5">
        <router-view />
      </div>
    </div>

    <CreateDialog v-model="showCreate" :config="currentConfig" @created="onCreateDone" />
    <PaymentDialog v-model="showPayment" @created="() => goList('payment-entry')" />
    <InvoiceFromOrderDialog v-model="showInvoice" @created="onInvoiceDone" />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Sidebar, Dropdown, Button, createResource } from 'frappe-ui'
import Home from '~icons/lucide/layout-dashboard'
import ExternalLink from '~icons/lucide/external-link'
import LogOut from '~icons/lucide/log-out'
import Plus from '~icons/lucide/plus'
import { LISTS, SECTIONS, findList } from '@/data/doctypes.js'
import CreateDialog from '@/components/dialogs/CreateDialog.vue'
import PaymentDialog from '@/components/dialogs/PaymentDialog.vue'
import InvoiceFromOrderDialog from '@/components/dialogs/InvoiceFromOrderDialog.vue'

const route = useRoute()
const router = useRouter()
const user = createResource({ url: 'frappe.auth.get_logged_user', auto: true })

const showCreate = ref(false)
const showPayment = ref(false)
const showInvoice = ref(false)
const currentConfig = ref(null)
const currentKey = ref('')

function openCreate(key) {
  const l = findList(key)
  currentConfig.value = l?.create || null
  currentKey.value = key
  showCreate.value = true
}
function goList(key) {
  router.push(`/list/${key}`)
}
function onCreateDone() {
  if (currentKey.value) goList(currentKey.value)
}
function onInvoiceDone(out) {
  goList((out?.doctype || 'Sales Invoice').toLowerCase().replace(/ /g, '-'))
}

const createOptions = [
  { label: 'New Sales Invoice', onClick: () => openCreate('sales-invoice') },
  { label: 'New Sales Order', onClick: () => openCreate('sales-order') },
  { label: 'New Purchase Invoice', onClick: () => openCreate('purchase-invoice') },
  { label: 'New Purchase Order', onClick: () => openCreate('purchase-order') },
  { label: 'New Item', onClick: () => openCreate('item') },
  { label: 'Record Payment…', onClick: () => (showPayment.value = true) },
  { label: 'Invoice from Order…', onClick: () => (showInvoice.value = true) },
]

const header = computed(() => ({
  title: 'Kamil Energy',
  subtitle: user.data || 'Jemkas Pharma Kenya Ltd',
  menuItems: [
    { label: 'Open ERPNext Desk', icon: ExternalLink, onClick: () => (window.location.href = '/app') },
    { label: 'Logout', icon: LogOut, onClick: () => (window.location.href = '/app/logout') },
  ],
}))

const sections = computed(() => {
  const dashboard = {
    items: [
      { label: 'Dashboard', to: '/dashboard', icon: Home, isActive: route.path === '/dashboard' || route.path === '/' },
    ],
  }
  const groups = SECTIONS.map((sec) => ({
    label: sec,
    items: LISTS.filter((l) => l.section === sec).map((l) => ({
      label: l.title,
      to: `/list/${l.key}`,
      icon: l.icon,
      isActive: route.params.key === l.key,
    })),
  }))
  return [dashboard, ...groups]
})

const pageTitle = computed(() => {
  if (route.params.key) return findList(route.params.key)?.title || 'List'
  return route.name || 'Kamil Energy'
})
</script>
