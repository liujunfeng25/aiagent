/**
 * 将后端返回的 ISO 时间格式化为北京时间显示（后端存的是北京时间，此处只取日期时间并标注 UTC+8，不依赖浏览器时区）
 * @param {string|null|undefined} iso - 如 "2026-03-09T05:47:56.320467"
 * @returns {string} 如 "2026-03-09 05:47 (UTC+8)" 或 "-"
 */
export function formatBeijingTime(iso) {
  if (iso == null || iso === '') return '-'
  const m = String(iso).match(/^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})/)
  if (m) return `${m[1]} ${m[2]}:${m[3]} (UTC+8)`
  return iso
}
