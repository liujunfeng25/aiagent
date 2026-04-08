<template>
  <canvas ref="canvasRef" class="tech-particle-bg" />
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'

const canvasRef = ref(null)
let rafId = 0
let resizeTimer = 0
let particles = []
let detachResize = null
let detachMouse = null

const mouse = {
  x: -9999,
  y: -9999,
  active: false,
  mode: 'attract',
}

function initParticles(width, height) {
  const baseCount = Math.floor((width * height) / 26000)
  const count = Math.min(160, Math.max(60, baseCount))
  particles = Array.from({ length: count }, () => ({
    x: Math.random() * width,
    y: Math.random() * height,
    vx: (Math.random() - 0.5) * 0.12,
    vy: (Math.random() - 0.5) * 0.12,
    drift: Math.random() * Math.PI * 2,
    blink: Math.random() * Math.PI * 2,
    r: 0.8 + Math.random() * 1.6,
  }))
}

function render(ctx, width, height, t) {
  ctx.clearRect(0, 0, width, height)

  const g = ctx.createRadialGradient(width * 0.5, height * 0.08, 20, width * 0.5, height * 0.55, width * 0.9)
  g.addColorStop(0, 'rgba(96,165,250,0.16)')
  g.addColorStop(0.55, 'rgba(51,65,120,0.06)')
  g.addColorStop(1, 'rgba(255,255,255,0)')
  ctx.fillStyle = g
  ctx.fillRect(0, 0, width, height)

  const maxDist = 140
  const mouseRadius = 190
  /** 略加强，全窗口跟随鼠标时更容易感知吸引/排斥 */
  const forceBase = 0.072

  for (let i = 0; i < particles.length; i += 1) {
    const p = particles[i]
    p.drift += 0.003
    p.blink += 0.04

    p.vx += Math.cos(p.drift + t * 0.0001) * 0.0012
    p.vy += Math.sin(p.drift + t * 0.0001) * 0.0012

    if (mouse.active) {
      const dxm = mouse.x - p.x
      const dym = mouse.y - p.y
      const dm = Math.hypot(dxm, dym) || 1
      if (dm < mouseRadius) {
        const k = (1 - dm / mouseRadius) * forceBase
        const s = mouse.mode === 'repel' ? -1 : 1
        p.vx += (dxm / dm) * k * s
        p.vy += (dym / dm) * k * s
      }
    }

    p.vx *= 0.992
    p.vy *= 0.992
    p.x += p.vx
    p.y += p.vy

    if (p.x < 0 || p.x > width) p.vx *= -1
    if (p.y < 0 || p.y > height) p.vy *= -1
    p.x = Math.max(0, Math.min(width, p.x))
    p.y = Math.max(0, Math.min(height, p.y))

    const twinkle = 0.45 + 0.55 * (0.5 + 0.5 * Math.sin(p.blink))
    const nodeAlpha = 0.35 + twinkle * 0.65

    ctx.beginPath()
    ctx.fillStyle = `rgba(125,211,252,${nodeAlpha.toFixed(3)})`
    ctx.shadowBlur = 2 + twinkle * 5
    ctx.shadowColor = 'rgba(56,189,248,0.75)'
    ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
    ctx.fill()
    ctx.shadowBlur = 0

    for (let j = i + 1; j < particles.length; j += 1) {
      const q = particles[j]
      const dx = p.x - q.x
      const dy = p.y - q.y
      const d = Math.hypot(dx, dy)
      if (d > maxDist) continue
      const ratio = 1 - d / maxDist
      const alpha = ratio * 0.32
      ctx.strokeStyle = `rgba(56,189,248,${alpha.toFixed(3)})`
      ctx.lineWidth = 0.6 + ratio * 1.2
      ctx.shadowBlur = 6 * ratio
      ctx.shadowColor = 'rgba(34,211,238,0.55)'
      ctx.beginPath()
      ctx.moveTo(p.x, p.y)
      ctx.lineTo(q.x, q.y)
      ctx.stroke()
      ctx.shadowBlur = 0
    }
  }
}

function start() {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const fit = () => {
    const w = canvas.clientWidth
    const h = canvas.clientHeight
    if (!w || !h) return
    const dpr = window.devicePixelRatio || 1
    canvas.width = Math.floor(w * dpr)
    canvas.height = Math.floor(h * dpr)
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    initParticles(w, h)
  }

  fit()

  const onResize = () => {
    window.clearTimeout(resizeTimer)
    resizeTimer = window.setTimeout(fit, 120)
  }

  /**
   * 画布在 App 里挂了 pointer-events:none，不能直接监听 canvas。
   * 用 window 追踪鼠标并映射到画布坐标，全页移动都有吸引/排斥。
   */
  const syncMouse = (e) => {
    const rect = canvas.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top
    mouse.x = Math.max(0, Math.min(canvas.clientWidth || rect.width, x))
    mouse.y = Math.max(0, Math.min(canvas.clientHeight || rect.height, y))
    mouse.active = true
  }

  const onWinMove = (e) => syncMouse(e)
  const onWinDown = (e) => {
    mouse.mode = e.button === 2 ? 'repel' : 'attract'
    syncMouse(e)
  }
  const onWinUp = () => {
    mouse.mode = 'attract'
  }
  const onBlur = () => {
    mouse.active = false
  }

  window.addEventListener('resize', onResize)
  window.addEventListener('mousemove', onWinMove)
  window.addEventListener('mousedown', onWinDown)
  window.addEventListener('mouseup', onWinUp)
  window.addEventListener('blur', onBlur)

  detachResize = () => window.removeEventListener('resize', onResize)
  detachMouse = () => {
    window.removeEventListener('mousemove', onWinMove)
    window.removeEventListener('mousedown', onWinDown)
    window.removeEventListener('mouseup', onWinUp)
    window.removeEventListener('blur', onBlur)
  }

  const tick = () => {
    render(ctx, canvas.clientWidth, canvas.clientHeight, performance.now())
    rafId = requestAnimationFrame(tick)
  }
  tick()
}

onMounted(start)
onUnmounted(() => {
  if (detachResize) detachResize()
  if (detachMouse) detachMouse()
  if (rafId) cancelAnimationFrame(rafId)
  if (resizeTimer) window.clearTimeout(resizeTimer)
})
</script>

<style scoped>
.tech-particle-bg {
  width: 100%;
  height: 100%;
  display: block;
}
</style>
