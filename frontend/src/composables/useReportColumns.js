// Column visibility for any report table, remembered per report in localStorage so a
// user's choice survives a reload. Used by both the query reports and the Report tab
// of each list view.
import { ref, computed, watch, unref } from 'vue'

export function useReportColumns(columns, storageKey) {
  const hidden = ref(new Set())

  function load() {
    try {
      const raw = localStorage.getItem(unref(storageKey))
      hidden.value = new Set(raw ? JSON.parse(raw) : [])
    } catch (e) {
      hidden.value = new Set()
    }
  }

  function persist() {
    try {
      localStorage.setItem(unref(storageKey), JSON.stringify([...hidden.value]))
    } catch (e) {
      /* private browsing — visibility just won't persist */
    }
  }

  function toggleColumn(fieldname) {
    const next = new Set(hidden.value)
    if (next.has(fieldname)) next.delete(fieldname)
    else next.add(fieldname)
    // Never let the last column be hidden — the table would be unreadable.
    if (next.size >= unref(columns).length) return
    hidden.value = next
    persist()
  }

  function showAllColumns() {
    hidden.value = new Set()
    persist()
  }

  const visibleColumns = computed(() => unref(columns).filter((c) => !hidden.value.has(c.fieldname)))
  const hiddenCount = computed(() => unref(columns).length - visibleColumns.value.length)

  // Checkbox-style menu: a tick against every column that is currently shown.
  const columnOptions = computed(() => [
    {
      group: 'Show columns',
      items: unref(columns).map((c) => ({
        label: `${hidden.value.has(c.fieldname) ? '☐' : '☑'}  ${c.label || c.fieldname}`,
        onClick: () => toggleColumn(c.fieldname),
      })),
    },
  ])

  watch(() => unref(storageKey), load, { immediate: true })

  return { hidden, visibleColumns, hiddenCount, columnOptions, toggleColumn, showAllColumns, reload: load }
}
