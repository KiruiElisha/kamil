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
      class="absolute right-0 z-50 mt-2 w-[min(22rem,calc(100vw-1.5rem))] overflow-hidden rounded-lg border border-outline-gray-2 bg-surface-white shadow-2xl"
    >
      <div class="flex items-center justify-between border-b border-outline-gray-1 px-3 py-2">
        <span class="text-sm font-semibold text-ink-gray-8">Notifications</span>
        <div class="flex items-center gap-3">
          <button
            v-if="unread"
            class="text-xs text-ink-gray-5 hover:text-ink-gray-8"
            @click="markAllRead"
          >
            Mark all read
          </button>
          <button class="text-xs text-ink-gray-5 hover:text-ink-gray-8" :disabled="loading" @click="load">
            {{ loading ? 'Refreshing…' : 'Refresh' }}
          </button>
        </div>
      </div>

      <div v-if="loading && !items.length && !system.length" class="space-y-2 p-3">
        <Skeleton v-for="n in 3" :key="n" class="h-8 w-full" />
      </div>
      <div v-else-if="!items.length && !system.length" class="p-6 text-center text-sm text-ink-gray-5">
        Nothing pending. All clear.
      </div>
      <div v-else class="max-h-[60vh] overflow-y-auto">
        <!-- Work that needs attention, counted from the documents themselves -->
        <template v-if="items.length">
          <div class="bg-surface-gray-1 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-ink-gray-5">
            Needs attention
          </div>
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
        </template>

        <!-- The same mentions / assignments / shares / alerts the desk bell shows -->
        <template v-if="system.length">
          <div class="bg-surface-gray-1 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-ink-gray-5">
            System notifications
          </div>
          <button
            v-for="n in system"
            :key="n.name"
            class="flex w-full items-start gap-2.5 border-b border-outline-gray-1 px-3 py-2.5 text-left last:border-0 hover:bg-surface-gray-2"
            :class="n.read ? '' : 'bg-blue-50/60'"
            @click="openNotification(n)"
          >
            <span class="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full" :class="n.read ? 'bg-gray-300' : dotClass(n.color)" />
            <span class="min-w-0 flex-1">
              <span class="block truncate text-sm" :class="n.read ? 'text-ink-gray-7' : 'font-medium text-ink-gray-8'">
                {{ n.subject || n.type }}
              </span>
              <span class="block truncate text-xs text-ink-gray-5">{{ subtitle(n) }}</span>
            </span>
            <Badge v-if="n.type" :theme="badgeTheme(n.color)" :label="n.type" />
          </button>
        </template>
      </div>
    </div>

    <!-- A notification opens here rather than throwing the user into the desk -->
    <Dialog v-model="detailOpen" :options="{ title: detail?.type || 'Notification', size: 'lg' }">
      <template #body-content>
        <div v-if="detail" class="space-y-3">
          <div class="flex flex-wrap items-center gap-2">
            <Badge :theme="badgeTheme(detail.color)" :label="detail.type" />
            <span class="text-xs text-ink-gray-5">{{ subtitle(detail) }}</span>
          </div>
          <div class="text-sm font-medium text-ink-gray-8">{{ detail.subject }}</div>
          <div
            v-if="detail.body"
            class="max-h-[50vh] overflow-auto rounded-lg border border-outline-gray-1 bg-surface-gray-1 p-3 text-sm text-ink-gray-7"
            v-html="detail.body"
          />
          <div v-if="detail.doctype" class="text-xs text-ink-gray-5">
            {{ detail.doctype }}<span v-if="detail.document"> · {{ detail.document }}</span>
          </div>
        </div>
      </template>
      <template #actions>
        <div class="flex flex-wrap justify-end gap-2">
          <Button label="Close" @click="detailOpen = false" />
          <Button v-if="detail?.doctype && detail?.document" label="Open in app" @click="openInApp(detail)" />
          <Button v-if="detail?.link || detail?.doctype" variant="solid" label="Open in ERPNext" @click="openInDesk(detail)" />
        </div>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { Badge, Button, Dialog, call } from 'frappe-ui'
import Bell from '~icons/lucide/bell'
import Skeleton from '@/components/Skeleton.vue'
import { findListByDoctype } from '@/data/doctypes.js'
import { dotClass } from '@/utils/status.js'
import { haptic } from '@/utils/haptics'

const router = useRouter()

const open = ref(false)
const loading = ref(false)
const items = ref([])
const system = ref([])
const unread = ref(0)
const total = ref(0)

async function load() {
  loading.value = true
  try {
    const res = await call('kamil.api.get_notifications')
    items.value = res?.items || []
    system.value = res?.system || []
    unread.value = res?.unread || 0
    total.value = res?.total || 0
  } catch (e) {
    // A bell that cannot load is not worth an error banner — just show nothing.
    items.value = []
    system.value = []
    unread.value = 0
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

function badgeTheme(color) {
  return color === 'amber' ? 'orange' : color || 'gray'
}

function subtitle(n) {
  const parts = []
  if (n.from_user_name || n.from_user) parts.push(n.from_user_name || n.from_user)
  if (n.doctype) parts.push(n.document ? `${n.doctype} · ${n.document}` : n.doctype)
  if (n.creation) parts.push(ago(n.creation))
  return parts.join(' · ')
}

function ago(value) {
  const then = new Date(String(value).replace(' ', 'T'))
  const mins = Math.round((Date.now() - then.getTime()) / 60000)
  if (!Number.isFinite(mins)) return ''
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  if (mins < 60 * 24) return `${Math.round(mins / 60)}h ago`
  return then.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })
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

// A notification opens in a modal: the app is the place people work, and bouncing
// them into the desk to read one line loses their place.
const detailOpen = ref(false)
const detail = ref(null)

async function openNotification(n) {
  detail.value = { ...n, body: n.email_content || '' }
  detailOpen.value = true

  if (!n.read) {
    n.read = 1
    unread.value = Math.max(unread.value - 1, 0)
    total.value = Math.max(total.value - 1, 0)
    try {
      await call('kamil.api.mark_notification_read', { name: n.name })
    } catch (e) {
      /* the badge is already updated; a failed flag is not worth interrupting for */
    }
  }
}

/** The app's own list for that doctype, when it has one. */
function openInApp(n) {
  const cfg = findListByDoctype(n.doctype)
  detailOpen.value = false
  open.value = false
  if (cfg) router.push({ path: `/list/${cfg.key}` })
  else openInDesk(n)
}

function openInDesk(n) {
  const target =
    n.link || (n.doctype && n.document
      ? `/app/${n.doctype.toLowerCase().replace(/ /g, '-')}/${encodeURIComponent(n.document)}`
      : '')
  if (!target) return
  detailOpen.value = false
  open.value = false
  window.location.href = target
}

async function markAllRead() {
  system.value.forEach((n) => (n.read = 1))
  total.value = Math.max(total.value - unread.value, 0)
  unread.value = 0
  try {
    await call('kamil.api.mark_all_notifications_read')
  } catch (e) {
    load() // put the real state back if the server disagreed
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
