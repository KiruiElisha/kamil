<template>
  <nav class="flex h-14 shrink-0 items-stretch border-t border-outline-gray-1 bg-surface-white md:hidden">
    <button
      v-for="t in visibleTabs"
      :key="t.key"
      class="flex flex-1 flex-col items-center justify-center gap-0.5 text-[11px] transition-colors"
      :class="isActive(t) ? 'text-ink-gray-9' : 'text-ink-gray-5'"
      @click="onTab(t)"
    >
      <component :is="t.icon" class="h-5 w-5" />
      <span>{{ t.label }}</span>
    </button>
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Home from '~icons/lucide/layout-dashboard'
import Receipt from '~icons/lucide/receipt'
import ShoppingBag from '~icons/lucide/shopping-bag'
import CreditCard from '~icons/lucide/credit-card'
import MenuIcon from '~icons/lucide/menu'
import { haptic } from '@/utils/haptics'
import { usePermissions } from '@/composables/usePermissions'

const emit = defineEmits(['more'])
const route = useRoute()
const router = useRouter()
const { canRead } = usePermissions()

const tabs = [
  { key: 'dashboard', label: 'Home', icon: Home, to: '/dashboard' },
  { key: 'sales-invoice', label: 'Sales', icon: Receipt, to: '/list/sales-invoice', doctype: 'Sales Invoice' },
  { key: 'purchase-invoice', label: 'Buying', icon: ShoppingBag, to: '/list/purchase-invoice', doctype: 'Purchase Invoice' },
  { key: 'payment-entry', label: 'Pay', icon: CreditCard, to: '/list/payment-entry', doctype: 'Payment Entry' },
  { key: 'more', label: 'More', icon: MenuIcon, more: true },
]

// Home and More always stay; the document tabs need read access to their doctype.
const visibleTabs = computed(() => tabs.filter((t) => !t.doctype || canRead(t.doctype)))

function isActive(t) {
  if (t.more) return false
  if (t.to === '/dashboard') return route.path === '/dashboard' || route.path === '/'
  return route.params.key === t.key
}
function onTab(t) {
  haptic()
  if (t.more) emit('more')
  else router.push(t.to)
}
</script>
