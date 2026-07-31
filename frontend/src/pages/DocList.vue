<template>
  <div class="mx-auto flex w-full min-h-0 max-w-6xl flex-1 flex-col gap-3 p-3 md:p-5">
    <template v-if="cfg">
      <Tabs class="!flex-none" v-model="tab" :tabs="tabs" />
      <DocTable v-show="tab === 0" :key="cfg.doctype" v-bind="tableProps" />
      <ListInsights v-if="tab === 1" :key="cfg.doctype + '-insights'" :doctype="cfg.doctype" :title="cfg.title" />
      <ListReport v-if="tab === 2" :key="cfg.doctype + '-report'" :doctype="cfg.doctype" :title="cfg.title" />
      <ListReportTab
        v-for="(t, i) in cfg.reportTabs || []"
        :key="cfg.doctype + '-' + t.report"
        v-show="tab === 3 + i"
        :report-key="t.report"
        :party-type="t.partyType || ''"
      />
    </template>
    <div v-else class="p-6 text-center text-sm text-ink-gray-5">Unknown list.</div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Tabs } from 'frappe-ui'
import ListIcon from '~icons/lucide/list'
import BarChart from '~icons/lucide/bar-chart-3'
import Table from '~icons/lucide/table-2'
import DocTable from '@/components/DocTable.vue'
import ListInsights from '@/components/ListInsights.vue'
import ListReport from '@/components/ListReport.vue'
import ListReportTab from '@/components/ListReportTab.vue'
import Wallet from '~icons/lucide/wallet'
import { findList } from '@/data/doctypes.js'

const route = useRoute()
const cfg = computed(() => findList(route.params.key))

const tab = ref(0)
// A list can declare extra tabs that embed a report (AR/GL on customers, AP/GL on
// suppliers), which is why the tab set is per-list rather than fixed.
const tabs = computed(() => [
  { label: 'List', icon: ListIcon },
  { label: 'Insights', icon: BarChart },
  { label: 'Report', icon: Table },
  ...(cfg.value?.reportTabs || []).map((t) => ({ label: t.label, icon: Wallet })),
])
// reset to the List tab whenever we switch doctypes
watch(() => route.params.key, () => (tab.value = 0))

const tableProps = computed(() => {
  const c = cfg.value
  return {
    title: c.title,
    doctype: c.doctype,
    columns: c.columns,
    viewFields: c.view || null,
    orderBy: c.orderBy,
    currencyField: c.currencyField ?? 'currency',
    createConfig: c.create || null,
    special: c.special || '',
  }
})
</script>
