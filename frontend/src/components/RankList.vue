<template>
  <div class="rounded-xl border border-outline-gray-1 bg-surface-white p-4">
    <h3 class="mb-3 text-sm font-semibold text-ink-gray-8">{{ title }}</h3>
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

const props = defineProps({
  title: String,
  rows: { type: Array, default: () => [] },
  currency: { type: String, default: 'KES' },
  money: { type: Boolean, default: true },
  barClass: { type: String, default: 'bg-blue-500' },
  partyType: { type: String, default: '' },
})

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
    return new Intl.NumberFormat('en-KE', { style: 'currency', currency: props.currency || 'KES', maximumFractionDigits: 0 }).format(v || 0)
  } catch {
    return v
  }
}
function fmtNum(v) {
  return new Intl.NumberFormat('en-KE').format(v || 0)
}
</script>
