import { sxVar } from './sxCss.js'

/* ── tooltip：深底 + 金边 + 毛玻璃 ── */
export function sxTooltip(overrides = {}) {
  return {
    trigger: 'axis',
    backgroundColor: sxVar('--sx-chart-tooltip-bg'),
    borderColor: 'rgba(103, 232, 249, 0.4)',
    borderWidth: 1,
    textStyle: {
      color: '#f8fafc',
      fontSize: 13,
      textShadowBlur: 3,
      textShadowColor: 'rgba(0,0,0,0.4)',
    },
    extraCssText:
      'backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);' +
      'box-shadow:0 0 20px rgba(34,211,238,0.15);border-radius:6px;',
    ...overrides,
  }
}

/* ── X 轴基线 ── */
export function sxAxisX(overrides = {}) {
  return {
    axisLabel: {
      color: sxVar('--sx-chart-axis-muted'),
      fontSize: 11,
      textShadowBlur: 4,
      textShadowColor: 'rgba(0,0,0,0.5)',
      ...(overrides.axisLabel || {}),
    },
    axisLine: {
      lineStyle: {
        color: sxVar('--sx-chart-axis-line-cyan'),
        shadowBlur: 6,
        shadowColor: 'rgba(34,211,238,0.18)',
        ...(overrides.axisLine?.lineStyle || {}),
      },
    },
    splitLine: overrides.splitLine,
    ...Object.fromEntries(
      Object.entries(overrides).filter(
        ([k]) => !['axisLabel', 'axisLine', 'splitLine'].includes(k),
      ),
    ),
  }
}

/* ── Y 轴基线 ── */
export function sxAxisY(overrides = {}) {
  return {
    axisLabel: {
      color: sxVar('--sx-chart-axis-muted'),
      fontSize: 11,
      textShadowBlur: 4,
      textShadowColor: 'rgba(0,0,0,0.5)',
      ...(overrides.axisLabel || {}),
    },
    splitLine: {
      lineStyle: {
        color: sxVar('--sx-chart-split-cyan'),
        shadowBlur: 3,
        shadowColor: 'rgba(34,211,238,0.08)',
        ...(overrides.splitLine?.lineStyle || {}),
      },
    },
    axisLine: overrides.axisLine
      ? {
          lineStyle: {
            shadowBlur: 6,
            shadowColor: 'rgba(34,211,238,0.18)',
            ...(overrides.axisLine?.lineStyle || {}),
          },
          ...Object.fromEntries(
            Object.entries(overrides.axisLine).filter(([k]) => k !== 'lineStyle'),
          ),
        }
      : undefined,
    ...Object.fromEntries(
      Object.entries(overrides).filter(
        ([k]) => !['axisLabel', 'splitLine', 'axisLine'].includes(k),
      ),
    ),
  }
}

/* ── grid 基线 ── */
export function sxGrid(overrides = {}) {
  return { top: 18, right: 14, bottom: 32, left: 52, ...overrides }
}

/* ── 发光快捷 ── */
export function sxGlow(color, blur = 8) {
  return { shadowBlur: blur, shadowColor: color }
}

/* ── 全局动画基线 ── */
export const sxAnimation = {
  animationDuration: 1200,
  animationEasing: 'cubicInOut',
  animationDurationUpdate: 600,
}
