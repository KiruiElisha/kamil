<template>
  <div class="min-h-0 flex-1 space-y-4 overflow-auto">
    <template v-if="loading">
      <div class="grid grid-cols-2 gap-3 sm:grid-cols-4"><Skeleton v-for="n in 4" :key="n" class="h-[86px]" /></div>
      <div class="grid gap-4 lg:grid-cols-2"><Skeleton class="h-72" /><Skeleton class="h-72" /></div>
    </template>
    <template v-else-if="data">
      <div v-if="data.kpis.length" class="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div v-for="k in data.kpis" :key="k.label" class="rounded-xl border border-outline-gray-1 bg-surface-white p-4">
          <div class="flex items-center gap-1.5">
            <span class="h-1.5 w-1.5 shrink-0 rounded-full" :class="DOT[k.color] || 'bg-gray-400'" />
            <span class="truncate text-xs text-ink-gray-5">{{ k.label }}</span>
          </div>
          <div class="mt-1 truncate text-xl font-semibold text-ink-gray-9">{{ kval(k) }}</div>
        </div>
      </div>

      <div v-if="data.monthly.length" class="h-72 rounded-xl border border-outline-gray-1 bg-surface-white p-3">
        <AxisChart :config="chart" />
      </div>

      <div class="grid gap-4 lg:grid-cols-2">
        <div v-if="data.status.length" class="h-72 rounded-xl border border-outline-gray-1 bg-surface-white p-3">
          <DonutChart :config="statusDonut" />
        </div>
        <RankList
          v-if="data.top_parties.length"
          :title="data.party_type === 'Supplier' ? 'Top Suppliers' : 'Top Customers'"
          :rows="data.top_parties"
          :currency="data.currency"
          bar-class="bg-blue-500"
          :party-type="data.party_type"
        />
      </div>

      <div v-if="!data.kpis.length && !data.monthly.length && !data.status.length" class="rounded-xl border border-outline-gray-1 bg-surface-white p-8 text-center text-sm text-ink-gray-5">
        No insights available for this list.
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { AxisChart, DonutChart, call } from 'frappe-ui'
import Skeleton from '@/components/Skeleton.vue'
import RankList from '@/components/RankList.vue'

const props = defineProps({ doctype: { type: String, required: true }, title: String })

const data = ref(null)
const loading = ref(true)

onMounted(async () => {
  try {
    data.value = await call('kamil.api.get_list_analytics', { doctype: props.doctype })
  } catch (e) {
    data.value = { currency: 'KES', kpis: [], status: [], top_parties: [], monthly: [], party_type: '' }
  } finally {
    loading.value = false
  }
})

const DOT = { green: 'bg-green-500', blue: 'bg-blue-500', orange: 'bg-orange-500', amber: 'bg-amber-500' }

function kval(k) {
  return k.money
    ? new Intl.NumberFormat('en-KE', { style: 'currency', currency: data.value.currency || 'KES', maximumFractionDigits: 0 }).format(k.value || 0)
    : new Intl.NumberFormat('en-KE').format(k.value || 0)
}

const chart = computed(() => ({
  data: data.value?.monthly || [],
  title: `${props.title || props.doctype} — last 6 months`,
  xAxis: { key: 'label', type: 'category' },
  yAxis: { title: '' },
  series: [{ name: 'total', type: 'bar', color: '#2563eb' }],
}))

const statusDonut = computed(() => ({
  data: data.value?.status || [],
  title: 'By status',
  categoryColumn: 'label',
  valueColumn: 'value',
  maxSliceCount: 8,
}))
</script>
