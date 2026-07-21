<template>
  <div
    class="flex h-screen w-screen overflow-hidden bg-surface-white"
    @touchstart.passive="onTouchStart"
    @touchmove.passive="onTouchMove"
  >
    <!-- Backdrop (mobile only) -->
    <div v-if="mobileNav" class="fixed inset-0 z-30 bg-black/40 md:hidden" @click="mobileNav = false" />

    <!-- Sidebar: static on desktop, off-canvas drawer on mobile -->
    <div
      class="fixed left-0 top-0 z-40 h-full shadow-2xl transition-transform duration-200 ease-in-out md:static md:z-auto md:translate-x-0 md:shadow-none"
      :class="mobileNav ? 'translate-x-0' : '-translate-x-full md:translate-x-0'"
    >
      <Sidebar :header="header" :sections="sections" :disable-collapse="isMobile" />
    </div>

    <div class="flex min-w-0 flex-1 flex-col overflow-hidden">
      <header class="flex h-12 shrink-0 items-center justify-between gap-2 border-b border-outline-gray-1 px-3 md:px-5">
        <div class="flex min-w-0 items-center gap-2">
          <button
            class="-ml-1 flex h-8 w-8 items-center justify-center rounded text-ink-gray-7 hover:bg-surface-gray-3 md:hidden"
            @click="openDrawer"
            aria-label="Menu"
          >
            <Menu class="h-5 w-5" />
          </button>
          <span class="truncate text-base font-semibold text-ink-gray-8">{{ pageTitle }}</span>
        </div>
        <Dropdown :options="createOptions">
          <Button variant="solid">
            <template #prefix><Plus class="h-4 w-4" /></template>
            <span class="hidden sm:inline">Create</span>
          </Button>
        </Dropdown>
      </header>

      <main class="flex min-h-0 flex-1 flex-col bg-surface-gray-1">
        <router-view />
      </main>

      <BottomNav @more="openDrawer" />
    </div>

    <CreateDialog v-model="showCreate" :config="currentConfig" @created="onCreateDone" />
    <PaymentDialog v-model="showPayment" @created="() => goList('payment-entry')" />
    <InvoiceFromOrderDialog v-model="showInvoice" @created="onInvoiceDone" />
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Sidebar, Dropdown, Button, createResource } from 'frappe-ui'
import Home from '~icons/lucide/layout-dashboard'
import ExternalLink from '~icons/lucide/external-link'
import LogOut from '~icons/lucide/log-out'
import Plus from '~icons/lucide/plus'
import Menu from '~icons/lucide/menu'
import { LISTS, SECTIONS, findList } from '@/data/doctypes.js'
import CreateDialog from '@/components/dialogs/CreateDialog.vue'
import PaymentDialog from '@/components/dialogs/PaymentDialog.vue'
import InvoiceFromOrderDialog from '@/components/dialogs/InvoiceFromOrderDialog.vue'
import BottomNav from '@/components/BottomNav.vue'
import { haptic } from '@/utils/haptics'
import { useIsMobile } from '@/composables/useIsMobile'

const route = useRoute()
const router = useRouter()
const user = createResource({ url: 'frappe.auth.get_logged_user', auto: true })

const isMobile = useIsMobile()
const mobileNav = ref(false)
watch(() => route.fullPath, () => (mobileNav.value = false))
function openDrawer() {
  haptic()
  mobileNav.value = true
}

// Edge-swipe to open / swipe to close the drawer (mobile)
let sx = 0
let sy = 0
let edge = false
function onTouchStart(e) {
  const t = e.touches[0]
  sx = t.clientX
  sy = t.clientY
  edge = t.clientX < 24
}
function onTouchMove(e) {
  const t = e.touches[0]
  const dx = t.clientX - sx
  const dy = Math.abs(t.clientY - sy)
  if (dy > 45) return
  if (!mobileNav.value && edge && dx > 55) openDrawer()
  else if (mobileNav.value && dx < -55) mobileNav.value = false
}

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
