// Lightweight tap haptic (Android Chrome / supported devices). No-op elsewhere.
export function haptic(ms = 8) {
  try {
    if (typeof navigator !== 'undefined' && navigator.vibrate) navigator.vibrate(ms)
  } catch (e) {
    /* ignore */
  }
}
