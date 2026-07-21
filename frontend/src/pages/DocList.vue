<template>
  <div class="mx-auto max-w-6xl">
    <DocTable v-if="cfg" :key="cfg.doctype" v-bind="tableProps" />
    <div v-else class="p-6 text-center text-sm text-ink-gray-5">Unknown list.</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import DocTable from '@/components/DocTable.vue'
import { findList } from '@/data/doctypes.js'

const route = useRoute()
const cfg = computed(() => findList(route.params.key))
const tableProps = computed(() => {
  const c = cfg.value
  return {
    title: c.title,
    doctype: c.doctype,
    columns: c.columns,
    orderBy: c.orderBy,
    currencyField: c.currencyField ?? 'currency',
    createConfig: c.create || null,
    special: c.special || '',
  }
})
</script>
