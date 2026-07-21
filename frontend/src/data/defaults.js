import { call } from 'frappe-ui'

let cache = null

export function getDefaults() {
  if (!cache) {
    cache = call('kamil.api.get_create_defaults').catch(() => ({}))
  }
  return cache
}
