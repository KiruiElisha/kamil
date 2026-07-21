import { onMounted, onUnmounted, ref } from 'vue'

// Attach touch pull-to-refresh to `rootRef`. Finds the inner scroller (ListView's
// .overflow-y-auto), and when the user pulls down while it's scrolled to the top,
// calls onRefresh(). Returns { distance, refreshing } for a visual indicator.
export function usePullToRefresh(rootRef, onRefresh, { threshold = 64 } = {}) {
  const distance = ref(0)
  const refreshing = ref(false)
  let startY = 0
  let active = false
  let scroller = null

  function findScroller(target) {
    let el = target
    while (el && el !== rootRef.value) {
      const oy = getComputedStyle(el).overflowY
      if ((oy === 'auto' || oy === 'scroll') && el.scrollHeight > el.clientHeight) return el
      el = el.parentElement
    }
    return rootRef.value ? rootRef.value.querySelector('.overflow-y-auto') : null
  }

  function onStart(e) {
    if (refreshing.value || e.touches.length !== 1) return
    scroller = findScroller(e.target)
    startY = e.touches[0].clientY
    active = !scroller || scroller.scrollTop <= 0
  }
  function onMove(e) {
    if (!active) return
    const dy = e.touches[0].clientY - startY
    if (dy > 0 && (!scroller || scroller.scrollTop <= 0)) {
      distance.value = Math.min(dy * 0.4, 90)
      if (distance.value > 3) e.preventDefault()
    } else {
      active = false
      distance.value = 0
    }
  }
  async function onEnd() {
    if (active && distance.value >= threshold * 0.5) {
      refreshing.value = true
      distance.value = 36
      try {
        await onRefresh()
      } catch (e) {
        /* ignore */
      } finally {
        refreshing.value = false
        distance.value = 0
      }
    } else {
      distance.value = 0
    }
    active = false
  }

  onMounted(() => {
    const el = rootRef.value
    if (!el) return
    el.addEventListener('touchstart', onStart, { passive: true })
    el.addEventListener('touchmove', onMove, { passive: false })
    el.addEventListener('touchend', onEnd, { passive: true })
    el.addEventListener('touchcancel', onEnd, { passive: true })
  })
  onUnmounted(() => {
    const el = rootRef.value
    if (!el) return
    el.removeEventListener('touchstart', onStart)
    el.removeEventListener('touchmove', onMove)
    el.removeEventListener('touchend', onEnd)
    el.removeEventListener('touchcancel', onEnd)
  })

  return { distance, refreshing }
}
