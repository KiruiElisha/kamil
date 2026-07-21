import { ref, onMounted, onUnmounted } from 'vue'

// Reactive flag: true when viewport is below `bp` px (default md breakpoint).
export function useIsMobile(bp = 768) {
  const isMobile = ref(false)
  function update() {
    isMobile.value = window.innerWidth < bp
  }
  onMounted(() => {
    update()
    window.addEventListener('resize', update)
  })
  onUnmounted(() => window.removeEventListener('resize', update))
  return isMobile
}
