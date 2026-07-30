<template>
  <div class="rounded-xl border border-outline-gray-1 bg-surface-white p-4">
    <div class="mb-3 flex items-center gap-2">
      <span v-if="icon" class="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg" :class="chip">
        <component :is="icon" class="h-4 w-4" />
      </span>
      <h3 class="truncate text-sm font-semibold text-ink-gray-8">{{ title }}</h3>
    </div>
    <div v-if="!rows.length" class="py-6 text-center text-sm text-ink-gray-5">No data for this period.</div>
    <component
      :is="partyType ? 'button' : 'div'"
      v-for="r in rows"
      :key="r.label"
      class="mb-3 block w-full text-left last:mb-0"
      :class="partyType ? 'cursor-pointer rounded hover:bg-surface-gray-1' : ''"
      @click="partyType && openLedger(r)"
    >
      <div class="flex items-baseline justify-between gap-3 text-sm">
        <span class="truncate text-ink-gray-7">{{ r.label }}</span>
        <span class="shrink-0 font-medium tabular-nums text-ink-gray-8">
          {{ money ? fmtMoney(r.value) : fmtNum(r.value) }}
        </span>
      </div>
      <div class="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-surface-gray-3">
        <div class="h-full rounded-full" :class="barClass" :style="{ width: pct(r.value) + '%' }" />
      </div>
      <div v-if="r.sub" class="mt-1 text-xs text-ink-gray-5">{{ r.sub }}</div>
    </component>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { defaultCurrency } from '@/utils/money.js'

const props = defineProps({
  title: String,
  rows: { type: Array, default: () => [] },
  currency: { type: String, default: '' },
  money: { type: Boolean, default: true },
  barClass: { type: String, default: 'bg-blue-500' },
  partyType: { type: String, default: '' },
  // Optional header icon, styled like the dashboard cards' chip.
  icon: { type: [Object, Function], default: null },
  color: { type: String, default: 'blue' },
})

// Mirrors StatCard's palette so a panel header and a card sit together well.
const CHIP = {
  green: 'bg-green-100 text-green-600',
  blue: 'bg-blue-100 text-blue-600',
  amber: 'bg-amber-100 text-amber-600',
  orange: 'bg-orange-100 text-orange-600',
  red: 'bg-red-100 text-red-600',
  violet: 'bg-violet-100 text-violet-600',
}
const chip = computed(() => CHIP[props.color] || CHIP.blue)

const router = useRouter()
function openLedger(r) {
  router.push({ path: '/report/general-ledger', query: { party_type: props.partyType, party: r.label } })
}

const max = computed(() => Math.max(1, ...props.rows.map((r) => Math.abs(r.value || 0))))
function pct(v) {
  return Math.max(2, Math.round((Math.abs(v || 0) / max.value) * 100))
}
function fmtMoney(v) {
  try {
    return new Intl.NumberFormat('en-KE', { style: 'currency', currency: props.currency || defaultCurrency(), maximumFractionDigits: 0 }).format(v || 0)
  } catch {
    return v
  }
}
function fmtNum(v) {
  return new Intl.NumberFormat('en-KE').format(v || 0)
}
</script>
