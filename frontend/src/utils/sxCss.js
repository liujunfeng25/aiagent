/**
 * 读取 :root 上的食迅设计 Token（供 ECharts option 等脚本使用）
 */
export function sxVar(name, root = typeof document !== 'undefined' ? document.documentElement : null) {
  if (!root || typeof getComputedStyle === 'undefined') return ''
  return getComputedStyle(root).getPropertyValue(name).trim()
}
