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
        <div class="flex shrink-0 items-center gap-1 sm:gap-2">
          <button
            class="flex h-8 w-8 items-center justify-center rounded text-ink-gray-7 hover:bg-surface-gray-3"
            title="Open Raven chat"
            aria-label="Open Raven chat"
            @click="openRaven"
          >
            <MessageSquare class="h-5 w-5" />
          </button>
          <NotificationBell />
          <Dropdown v-if="createOptions.length" :options="createOptions">
            <Button variant="solid">
              <template #prefix><Plus class="h-4 w-4" /></template>
              <span class="hidden sm:inline">Create</span>
            </Button>
          </Dropdown>
        </div>
      </header>

      <main class="flex min-h-0 flex-1 flex-col bg-surface-gray-1">
        <router-view />
      </main>

      <BottomNav @more="openDrawer" />
    </div>

    <CreateDialog v-model="showCreate" :config="currentConfig" @created="onCreateDone" />
    <PaymentDialog v-model="showPayment" @created="() => goList('payment-entry')" />
    <PaymentRequestDialog v-model="showRequest" @created="() => goList('payment-request')" />
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
import MessageSquare from '~icons/lucide/message-square'
import Landmark from '~icons/lucide/landmark'
import UsersIcon from '~icons/lucide/users'
import Mail from '~icons/lucide/mail'
import Settings from '~icons/lucide/settings'
import { SECTIONS, findList } from '@/data/doctypes.js'
import { findReport } from '@/data/reports.js'
import BarChart from '~icons/lucide/bar-chart-3'
import CreateDialog from '@/components/dialogs/CreateDialog.vue'
import PaymentDialog from '@/components/dialogs/PaymentDialog.vue'
import PaymentRequestDialog from '@/components/dialogs/PaymentRequestDialog.vue'
import InvoiceFromOrderDialog from '@/components/dialogs/InvoiceFromOrderDialog.vue'
import BottomNav from '@/components/BottomNav.vue'
import NotificationBell from '@/components/NotificationBell.vue'
import { haptic } from '@/utils/haptics'
import { useIsMobile } from '@/composables/useIsMobile'
import { usePermissions } from '@/composables/usePermissions'

const route = useRoute()
const router = useRouter()
const user = createResource({ url: 'frappe.auth.get_logged_user', auto: true })

const isMobile = useIsMobile()
const mobileNav = ref(false)
watch(() => route.fullPath, () => (mobileNav.value = false))
function openRaven() {
  haptic()
  window.open('/raven', '_blank')
}

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

// Permissions decide what the sidebar and the Create menu offer.
const { canRead, canCreate, visibleLists, visibleReports } = usePermissions()

const showCreate = ref(false)
const showPayment = ref(false)
const showRequest = ref(false)
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

// Only offer what the user may actually create.
const CREATE_MENU = [
  { key: 'sales-invoice', label: 'New Sales Invoice', doctype: 'Sales Invoice' },
  { key: 'sales-order', label: 'New Sales Order', doctype: 'Sales Order' },
  { key: 'purchase-invoice', label: 'New Purchase Invoice', doctype: 'Purchase Invoice' },
  { key: 'purchase-order', label: 'New Purchase Order', doctype: 'Purchase Order' },
  { key: 'item', label: 'New Item', doctype: 'Item' },
]

const createOptions = computed(() => {
  const options = CREATE_MENU.filter((m) => canCreate(m.doctype)).map((m) => ({
    label: m.label,
    onClick: () => openCreate(m.key),
  }))
  // Requesting a payment comes first: it is the intended route for every payment,
  // with the direct Payment Entry kept for corrections and opening balances.
  if (canCreate('Payment Request')) {
    options.push({ label: 'Request Payment…', onClick: () => (showRequest.value = true) })
  }
  if (canCreate('Payment Entry')) {
    options.push({ label: 'Record Payment directly…', onClick: () => (showPayment.value = true) })
  }
  if (canCreate('Sales Invoice') || canCreate('Purchase Invoice')) {
    options.push({ label: 'Invoice from Order…', onClick: () => (showInvoice.value = true) })
  }
  return options
})

const header = computed(() => ({
  title: 'Kamil Energy',
  subtitle: user.data || '',
  logo: '/assets/kamil/frontend/icon-192.png',
  menuItems: [
    { label: 'Open ERPNext Desk', icon: ExternalLink, onClick: () => (window.location.href = '/app') },
    { label: 'Logout', icon: LogOut, onClick: () => (window.location.href = '/app/logout') },
  ],
}))

const sections = computed(() => {
  const items = [
    { label: 'Dashboard', to: '/dashboard', icon: Home, isActive: route.path === '/dashboard' || route.path === '/' },
  ]
  // No point offering the Reports index if every report in it is off-limits.
  if (visibleReports.value.length) {
    items.push({
      label: 'Reports',
      to: '/reports',
      icon: BarChart,
      isActive: route.name === 'Reports' || route.name === 'Report',
    })
  }

  const groups = SECTIONS.map((sec) => ({
    label: sec,
    collapsible: true,
    items: visibleLists.value
      .filter((l) => l.section === sec)
      .map((l) => ({
        label: l.title,
        to: `/list/${l.key}`,
        icon: l.icon,
        isActive: route.name === 'List' && route.params.key === l.key,
      })),
  })).filter((g) => g.items.length) // drop sections the user has no access to at all

  // Setup lives at the bottom. Email is always there — it is the user's own mailbox —
  // while the rest follow read access to what they manage.
  const setup = []
  if (canRead('Account')) {
    setup.push({
      label: 'Chart of Accounts',
      to: '/chart-of-accounts',
      icon: Landmark,
      isActive: route.name === 'ChartOfAccounts',
    })
  }
  if (canRead('User')) {
    setup.push({ label: 'Users', to: '/users', icon: UsersIcon, isActive: route.name === 'Users' })
  }
  setup.push({ label: 'My Email', to: '/settings/email', icon: Mail, isActive: route.name === 'EmailSettings' })
  // Who payment approvals go to; readable by anyone, writable by a System Manager.
  setup.push({ label: 'Settings', to: '/settings/payments', icon: Settings, isActive: route.name === 'AppSettings' })

  return [{ items }, ...groups, { label: 'Setup', collapsible: true, items: setup }]
})

const PAGE_TITLES = {
  Reports: 'Reports',
  ChartOfAccounts: 'Chart of Accounts',
  Users: 'Users',
  EmailSettings: 'My Email',
  AppSettings: 'Settings',
  PaymentApproval: 'Payment Approval',
}

const pageTitle = computed(() => {
  if (PAGE_TITLES[route.name]) return PAGE_TITLES[route.name]
  if (route.name === 'Report') return findReport(route.params.key)?.title || 'Report'
  if (route.name === 'List' && route.params.key) return findList(route.params.key)?.title || 'List'
  return route.name || 'Kamil Energy'
})
</script>
