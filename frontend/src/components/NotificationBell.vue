<template>
  <div class="relative">
    <button
      class="relative flex h-8 w-8 items-center justify-center rounded text-ink-gray-7 hover:bg-surface-gray-3"
      :aria-label="total ? `${total} items need attention` : 'Notifications'"
      @click="toggle"
    >
      <Bell class="h-5 w-5" />
      <span
        v-if="total"
        class="absolute -right-0.5 -top-0.5 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-semibold leading-none text-white"
      >
        {{ total > 99 ? '99+' : total }}
      </span>
    </button>

    <!-- Click-away catcher; sits under the panel but over the page -->
    <div v-if="open" class="fixed inset-0 z-40" @click="open = false" />

    <div
      v-if="open"
      class="absolute right-0 z-50 mt-2 w-[min(20rem,calc(100vw-1.5rem))] overflow-hidden rounded-lg border border-outline-gray-2 bg-surface-white shadow-2xl"
    >
      <div class="flex items-center justify-between border-b border-outline-gray-1 px-3 py-2">
        <span class="text-sm font-semibold text-ink-gray-8">Needs attention</span>
        <button class="text-xs text-ink-gray-5 hover:text-ink-gray-8" :disabled="loading" @click="load">
          {{ loading ? 'Refreshing…' : 'Refresh' }}
        </button>
      </div>

      <div v-if="loading && !items.length" class="space-y-2 p-3">
        <Skeleton v-for="n in 3" :key="n" class="h-8 w-full" />
      </div>
      <div v-else-if="!items.length" class="p-6 text-center text-sm text-ink-gray-5">
        Nothing pending. All clear.
      </div>
      <div v-else class="max-h-[60vh] overflow-y-auto">
        <button
          v-for="i in items"
          :key="i.key"
          class="flex w-full items-center gap-2.5 border-b border-outline-gray-1 px-3 py-2.5 text-left last:border-0 hover:bg-surface-gray-2"
          @click="go(i)"
        >
          <span class="h-1.5 w-1.5 shrink-0 rounded-full" :class="dotClass(i.color)" />
          <span class="min-w-0 flex-1">
            <span class="block truncate text-sm text-ink-gray-8">{{ i.label }}</span>
            <span class="block truncate text-xs text-ink-gray-5">{{ i.doctype }}</span>
          </span>
          <Badge :theme="i.color === 'amber' ? 'orange' : i.color" :label="String(i.count)" />
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { Badge, call } from 'frappe-ui'
import Bell from '~icons/lucide/bell'
import Skeleton from '@/components/Skeleton.vue'
import { findListByDoctype } from '@/data/doctypes.js'
import { dotClass } from '@/utils/status.js'
import { haptic } from '@/utils/haptics'

const router = useRouter()

const open = ref(false)
const loading = ref(false)
const items = ref([])
const total = ref(0)

async function load() {
  loading.value = true
  try {
    const res = await call('kamil.api.get_notifications')
    items.value = res?.items || []
    total.value = res?.total || 0
  } catch (e) {
    // A bell that cannot load is not worth an error banner — just show nothing.
    items.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function toggle() {
  haptic()
  open.value = !open.value
  if (open.value) load()
}

// Clicking through takes you to the matching list, pre-filtered to the status the
// count was built from. Doctypes with no list in the app fall back to the desk.
function go(item) {
  open.value = false
  const cfg = findListByDoctype(item.doctype)
  if (cfg) {
    router.push({ path: `/list/${cfg.key}`, query: item.status ? { status: item.status } : {} })
  } else {
    window.location.href = `/app/${item.doctype.toLowerCase().replace(/ /g, '-')}`
  }
}

// Refresh in the background so the badge does not go stale on a long-lived tab.
let timer = null
onMounted(() => {
  load()
  timer = setInterval(load, 5 * 60 * 1000)
})
onUnmounted(() => timer && clearInterval(timer))
</script>
