// Server-sent icon names -> lucide components. KPIs are built server-side, so they
// name an icon rather than shipping a component; anything unknown falls back to a
// neutral one so a new KPI can never render a blank chip.
import Activity from '~icons/lucide/activity'
import Ban from '~icons/lucide/ban'
import Calendar from '~icons/lucide/calendar'
import CheckCircle from '~icons/lucide/check-circle'
import Clock from '~icons/lucide/clock'
import FileText from '~icons/lucide/file-text'
import Layers from '~icons/lucide/layers'
import Package from '~icons/lucide/package'
import PlusCircle from '~icons/lucide/plus-circle'
import Send from '~icons/lucide/send'
import TrendingUp from '~icons/lucide/trending-up'
import Users from '~icons/lucide/users'
import Wallet from '~icons/lucide/wallet'

const ICONS = {
  activity: Activity,
  ban: Ban,
  calendar: Calendar,
  'check-circle': CheckCircle,
  clock: Clock,
  'file-text': FileText,
  layers: Layers,
  package: Package,
  'plus-circle': PlusCircle,
  send: Send,
  'trending-up': TrendingUp,
  users: Users,
  wallet: Wallet,
}

/** Accepts a name, an already-resolved component, or nothing. */
export function iconFor(icon) {
  if (!icon) return Activity
  if (typeof icon !== 'string') return icon
  return ICONS[icon] || Activity
}
