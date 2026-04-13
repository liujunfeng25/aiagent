/** easeOutCubic，大屏数字缓动常用 */
export function easeOutCubic(t) {
  return 1 - (1 - t) ** 3
}

/**
 * 从 from 到 to 做时长 durationMs 的 RAF 插值，每帧回调 onFrame({ gmv, orders, avg, progress })。
 * @returns {() => void} 取消函数
 */
export function animateKpiTriple(from, to, { durationMs = 520, onFrame, onComplete } = {}) {
  let raf = 0
  const t0 = performance.now()
  const fg = Number(from.gmv) || 0
  const fo = Number(from.orders) || 0
  const fa = Number(from.avg) || 0
  const tg = Number(to.gmv) || 0
  const tov = Number(to.orders) || 0
  const ta = Number(to.avg) || 0

  const step = (now) => {
    const raw = Math.min(1, (now - t0) / durationMs)
    const e = easeOutCubic(raw)
    const gmv = fg + (tg - fg) * e
    const orders = fo + (tov - fo) * e
    const avg = fa + (ta - fa) * e
    onFrame?.({ gmv, orders, avg, progress: raw })
    if (raw < 1) {
      raf = requestAnimationFrame(step)
    } else {
      onFrame?.({ gmv: tg, orders: tov, avg: ta, progress: 1 })
      onComplete?.()
    }
  }
  raf = requestAnimationFrame(step)
  return () => {
    if (raf) cancelAnimationFrame(raf)
  }
}
