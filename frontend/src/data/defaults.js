import { call } from 'frappe-ui'
import { setDefaultCurrency } from '@/utils/money.js'

let cache = null

export function getDefaults() {
  if (!cache) {
    cache = call('kamil.api.get_create_defaults')
      .then((d) => {
        // Every amount in the app falls back to this when a record carries no
        // currency of its own.
        setDefaultCurrency(d?.currency)
        return d || {}
      })
      .catch(() => ({}))
  }
  return cache
}
