// One place that knows what currency to show when a record does not carry its own.
//
// The app used to fall back to a hard-coded "KES" in a dozen components, which is
// simply wrong on a company whose default currency is anything else. The fallback is
// now the company's own default, fetched once with the other create defaults; until
// that resolves (or if a site has none) amounts are formatted as plain numbers rather
// than being labelled with a currency nobody chose.

let companyCurrency = ''

export function setDefaultCurrency(currency) {
  if (currency) companyCurrency = currency
}

/** The company's default currency, or '' when it is not known yet. */
export function defaultCurrency() {
  return companyCurrency
}

/**
 * Format an amount. `currency` is whatever the record itself carries; anything
 * falsy falls back to the company default, then to a plain number.
 */
export function formatMoney(value, currency, options = {}) {
  if (value === null || value === undefined || value === '') return ''
  const code = currency || companyCurrency
  const opts = { maximumFractionDigits: 2, ...options }
  try {
    return code
      ? new Intl.NumberFormat('en-KE', { style: 'currency', currency: code, ...opts }).format(value)
      : new Intl.NumberFormat('en-KE', opts).format(value)
  } catch {
    return value
  }
}

/** Whole-currency amounts, for cards and lists where decimals are noise. */
export function formatMoneyShort(value, currency) {
  return formatMoney(value, currency, { maximumFractionDigits: 0 })
}
