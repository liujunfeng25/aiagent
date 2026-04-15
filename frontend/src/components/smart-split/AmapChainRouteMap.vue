<template>
  <div class="chain-map">
    <div v-if="errorText" class="chain-map__err">{{ errorText }}</div>
    <div
      v-else-if="missingDepotHint"
      class="chain-map__idle"
    >
      {{ missingDepotHint }}
    </div>
    <div v-else-if="loading" class="chain-map__loading" role="status" aria-live="polite">
      <div class="chain-map__loading-card">
        <el-icon class="is-loading chain-map__loading-icon" :size="26"><Loading /></el-icon>
        <div class="chain-map__loading-title">{{ progressTitle }}</div>
        <div class="chain-map__loading-detail">{{ progressDetail }}</div>
        <el-progress
          :percentage="progressPercent"
          :stroke-width="8"
          striped
          striped-flow
          :duration="12"
          class="chain-map__progress"
        />
        <div class="chain-map__loading-hint">地理编码完成后将按途径点分段请求高德驾车规划，点较多时请稍候</div>
      </div>
    </div>
    <div
      v-if="warnText && !loading && !errorText"
      class="chain-map__warn"
    >
      {{ warnText }}
    </div>
    <div ref="mapElRef" class="chain-map__canvas" />
  </div>
</template>

<script setup>
import { ref, computed, watch, onUnmounted, nextTick } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { fetchAmapJsConfig, geocodeSmartSplitAddresses } from '../../api/governanceDemo.js'

const LINE_COLOR = '#22d3ee'
/** 单次地理编码请求地址数上限（后端48）；留余量分批串联 */
const GEOCODE_CHUNK_SIZE = 40
/** 地图上标注略缩短，避免遮挡 */
const MAP_LABEL_MAX_LEN = 14

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function shortMapLabel(name) {
  const n = String(name || '').trim() || '—'
  if (n.length <= MAP_LABEL_MAX_LEN) return n
  return `${n.slice(0, MAP_LABEL_MAX_LEN)}…`
}

const props = defineProps({
  /** 起点（仓）地址全文 */
  depotAddress: { type: String, default: '' },
  /** 已按送货顺序排列的订单：member_address 必填 */
  orders: { type: Array, default: () => [] },
  /** 为 true 时触发加载（如父级拉完列表后） */
  ready: { type: Boolean, default: false },
})

const mapElRef = ref(null)
const loading = ref(false)
const errorText = ref('')
const warnText = ref('')
const progressTitle = ref('正在准备路线图')
const progressDetail = ref('')
const progressPercent = ref(0)

/** 父级已展示订单但 ready=false（多为缺少 depot）时避免纯黑画布 */
const missingDepotHint = computed(() => {
  if (props.ready) return ''
  const n = props.orders?.length ?? 0
  if (n <= 0) return ''
  const dep = String(props.depotAddress || '').trim()
  if (dep) {
    return ''
  }
  return '缺少起点仓地址（depot_address），无法绘制路线图。请确认接口返回或联系管理员配置。'
})

let mapInstance = null
let amapScriptPromise = null
let mapReadyFallbackTimer = null

function destroyMap() {
  if (mapReadyFallbackTimer != null) {
    clearTimeout(mapReadyFallbackTimer)
    mapReadyFallbackTimer = null
  }
  if (mapInstance) {
    try {
      mapInstance.destroy()
    } catch {
      /* ignore */
    }
    mapInstance = null
  }
}

function setProgress(pct, title, detail) {
  progressPercent.value = Math.min(100, Math.max(0, Math.round(pct)))
  if (title) progressTitle.value = title
  if (detail !== undefined) progressDetail.value = detail
}

function finishMapLoading() {
  if (!loading.value) {
    return
  }
  if (mapReadyFallbackTimer != null) {
    clearTimeout(mapReadyFallbackTimer)
    mapReadyFallbackTimer = null
  }
  setProgress(100, '地图已就绪', '驾车路线与标注已显示')
  loading.value = false
}

function loadAmapScript(key, securityJsCode) {
  if (window.AMap) return Promise.resolve(window.AMap)
  if (amapScriptPromise) return amapScriptPromise
  window._AMapSecurityConfig = { securityJsCode }
  amapScriptPromise = new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = `https://webapi.amap.com/maps?v=2.0&key=${encodeURIComponent(key)}`
    script.async = true
    script.onload = () => resolve(window.AMap)
    script.onerror = () => reject(new Error('高德地图脚本加载失败'))
    document.head.appendChild(script)
  })
  return amapScriptPromise
}

function loadAmapDrivingPlugin(AMap) {
  return new Promise((resolve, reject) => {
    try {
      if (AMap.Driving) {
        resolve()
        return
      }
      AMap.plugin(['AMap.Driving'], () => resolve())
    } catch (e) {
      reject(e)
    }
  })
}

/** 从驾车规划结果取出折线点序列 [[lng,lat], ...] */
function extractDrivingLngLatPath(result) {
  const routes = result?.routes
  if (!routes?.length) return null
  const route = routes[0]
  const steps = route?.steps
  if (!Array.isArray(steps) || !steps.length) return null
  const out = []
  for (const step of steps) {
    const pth = step?.path
    if (!Array.isArray(pth)) continue
    for (const p of pth) {
      if (p == null) continue
      if (typeof p.lng === 'number' && typeof p.lat === 'number') {
        out.push([p.lng, p.lat])
      } else if (Array.isArray(p) && p.length >= 2) {
        out.push([Number(p[0]), Number(p[1])])
      }
    }
  }
  return out.length ? out : null
}

function mergePathPoints(accum, segment) {
  if (!segment?.length) return
  for (const pt of segment) {
    const lng = Number(pt[0] ?? pt.lng)
    const lat = Number(pt[1] ?? pt.lat)
    if (Number.isNaN(lng) || Number.isNaN(lat)) continue
    const last = accum[accum.length - 1]
    if (last && Math.abs(last[0] - lng) < 1e-7 && Math.abs(last[1] - lat) < 1e-7) continue
    accum.push([lng, lat])
  }
}

/**
 * 按顺序对相邻途径点做驾车规划，合并为一条路径；单段失败则用直线连接该段起终点。
 */
async function buildDrivingPolylinePath(AMap, waypointLngLats, reportSegment) {
  if (!waypointLngLats || waypointLngLats.length < 2) {
    return waypointLngLats ? [...waypointLngLats] : []
  }
  await loadAmapDrivingPlugin(AMap)
  const policy = AMap.DrivingPolicy?.LEAST_TIME ?? 0
  const driving = new AMap.Driving({
    map: null,
    hideMarkers: true,
    policy,
  })
  const merged = []
  const nSeg = waypointLngLats.length - 1
  for (let i = 0; i < nSeg; i += 1) {
    reportSegment?.(i + 1, nSeg)
    await nextTick()
    const a = waypointLngLats[i]
    const b = waypointLngLats[i + 1]
    const segPath = await new Promise((resolve) => {
      try {
        driving.search(
          new AMap.LngLat(a[0], a[1]),
          new AMap.LngLat(b[0], b[1]),
          (status, result) => {
            if (status === 'complete') {
              resolve(extractDrivingLngLatPath(result))
            } else {
              resolve(null)
            }
          },
        )
      } catch {
        resolve(null)
      }
    })
    if (segPath?.length) {
      mergePathPoints(merged, segPath)
    } else {
      mergePathPoints(merged, [a, b])
    }
  }
  return merged.length >= 2 ? merged : waypointLngLats
}

async function buildRoute() {
  errorText.value = ''
  warnText.value = ''
  destroyMap()
  if (!props.ready || !props.depotAddress || !props.orders?.length) {
    loading.value = false
    return
  }

  loading.value = true
  setProgress(0, '正在准备路线图', '解析订单地址…')
  await nextTick()

  const stops = props.orders.map((o, i) => ({
    idx: i + 1,
    order_sn: String(o.order_sn ?? ''),
    /** 地图标记与 tooltip 用客户名 */
    label: String(o.customer_name || o.order_sn || `停${i + 1}`),
    address: String(o.member_address || '').trim(),
  }))
  if (stops.some((s) => !s.address)) {
    loading.value = false
    errorText.value = '存在订单缺少收货地址，无法排线。'
    ElMessage.warning(errorText.value)
    return
  }

  const toGeocode = [props.depotAddress, ...stops.map((s) => s.address)]
  const totalAddr = toGeocode.length
  const totalBatches = Math.max(1, Math.ceil(totalAddr / GEOCODE_CHUNK_SIZE))

  setProgress(4, '正在准备路线图', `共 ${totalAddr} 个地址待解析（含 1 个起点仓），将分 ${totalBatches} 批请求`)
  await nextTick()

  let cfg
  try {
    setProgress(6, '获取地图配置', '连接后端读取高德 JSAPI 配置…')
    cfg = await fetchAmapJsConfig()
  } catch (e) {
    loading.value = false
    errorText.value = typeof e === 'string' ? e : '获取地图配置失败'
    ElMessage.error(errorText.value)
    return
  }
  if (!cfg?.enabled || !cfg.key) {
    loading.value = false
    errorText.value = '未配置高德 JSAPI。'
    ElMessage.warning(errorText.value)
    return
  }

  setProgress(8, '地理编码中', `0 / ${totalAddr} 个地址 · 共 ${totalBatches} 批（即将请求第 1 批）`)
  await nextTick()

  const results = []
  try {
    let batchIndex = 0
    for (let off = 0; off < toGeocode.length; off += GEOCODE_CHUNK_SIZE) {
      batchIndex += 1
      const chunk = toGeocode.slice(off, off + GEOCODE_CHUNK_SIZE)
      setProgress(
        8 + (72 * off) / totalAddr,
        '地理编码中',
        `已完成 ${off} / ${totalAddr} 个地址 · 正请求第 ${batchIndex} / ${totalBatches} 批（每批最多 ${GEOCODE_CHUNK_SIZE} 条）`,
      )
      await nextTick()
      const geoRes = await geocodeSmartSplitAddresses({
        addresses: chunk,
        fallback_disabled: true,
        delivery_route_jjj: true,
      })
      const part = Array.isArray(geoRes?.results) ? geoRes.results : []
      if (part.length !== chunk.length) {
        loading.value = false
        errorText.value = '地理编码结果异常。'
        return
      }
      results.push(...part)
      const done = Math.min(off + chunk.length, totalAddr)
      setProgress(
        8 + (72 * done) / totalAddr,
        '地理编码中',
        `已完成 ${done} / ${totalAddr} 个地址 · 第 ${batchIndex} / ${totalBatches} 批已返回`,
      )
      await nextTick()
    }
  } catch (e) {
    loading.value = false
    errorText.value = typeof e === 'string' ? e : '地理编码失败'
    ElMessage.error(errorText.value)
    return
  }

  setProgress(82, '校验坐标', `已完成 ${totalAddr} 个地址的地理编码，正在校验经纬度…`)
  await nextTick()

  if (results.length !== toGeocode.length) {
    loading.value = false
    errorText.value = '地理编码结果异常。'
    return
  }

  /** 与 toGeocode 下标对齐；null 表示该点无坐标 */
  const coordsByIdx = []
  const failedLines = []
  for (let i = 0; i < results.length; i += 1) {
    const r = results[i]
    if (r?.lng != null && r?.lat != null) {
      coordsByIdx[i] = [Number(r.lng), Number(r.lat)]
    } else {
      coordsByIdx[i] = null
      if (i === 0) {
        loading.value = false
        errorText.value = `起点仓无法定位：${toGeocode[0]}`
        ElMessage.warning(errorText.value)
        return
      }
      const st = stops[i - 1]
      const tail = toGeocode[i] || ''
      failedLines.push(st ? `${st.idx}. ${st.label} · ${tail}` : tail)
    }
  }

  const path = coordsByIdx.filter((c) => c != null)
  if (!path.length) {
    loading.value = false
    errorText.value = '所有地址均未获得有效坐标。'
    return
  }

  if (failedLines.length) {
    const maxShow = 4
    const head = failedLines.slice(0, maxShow).join('；')
    const more = failedLines.length > maxShow ? ` … 共 ${failedLines.length} 处` : `（共 ${failedLines.length} 处）`
    warnText.value = `部分收货地址无法定位，已在折线中跳过，仍连接其余途径点：${head}${more}`
    ElMessage.warning(`有 ${failedLines.length} 个收货地址无法定位，地图已尽量展示其余路线。`)
  }

  let AMap
  try {
    setProgress(84, '加载地图脚本', '从高德 CDN 加载 JSAPI…')
    await nextTick()
    AMap = await loadAmapScript(cfg.key, cfg.securityJsCode)
  } catch (e) {
    loading.value = false
    errorText.value = typeof e === 'string' ? e : '地图加载失败'
    ElMessage.error(errorText.value)
    return
  }

  /** 途径点顺序的经纬度（与 path 一致），用于驾车分段规划 */
  let linePath = path
  if (path.length >= 2) {
    try {
      setProgress(86, '规划驾车路线', `按顺序规划 ${path.length - 1} 段驾车路径…`)
      await nextTick()
      linePath = await buildDrivingPolylinePath(AMap, path, (cur, total) => {
        const pct = 86 + (6 * cur) / Math.max(1, total)
        setProgress(pct, '规划驾车路线', `驾车路径 ${cur} / ${total} 段已完成…`)
      })
    } catch (e) {
      linePath = path
      warnText.value = `${warnText.value ? `${warnText.value} ` : ''}驾车规划异常，已改用途径点直线连接。`.trim()
    }
  }

  if (!mapElRef.value) {
    loading.value = false
    errorText.value = '地图容器未就绪'
    return
  }

  setProgress(93, '渲染地图', '创建地图并绘制驾车路线，随后加载底图瓦片…')
  await nextTick()

  const onMapReady = () => {
    if (mapReadyFallbackTimer != null) {
      clearTimeout(mapReadyFallbackTimer)
      mapReadyFallbackTimer = null
    }
    try {
      mapInstance?.off?.('complete', onMapReady)
    } catch {
      /* ignore */
    }
    finishMapLoading()
  }

  const depotCoord = coordsByIdx[0]
  mapInstance = new AMap.Map(mapElRef.value, {
    zoom: 11,
    viewMode: '2D',
    center: depotCoord,
  })

  const overlays = []

  const depotM = new AMap.Marker({
    position: depotCoord,
    title: `起点：${props.depotAddress}`,
    map: mapInstance,
  })
  depotM.setLabel({
    direction: 'top',
    content: '<div class="chain-map-marker chain-map-marker--depot">起点</div>',
    offset: new AMap.Pixel(0, -4),
  })
  overlays.push(depotM)

  for (let i = 0; i < stops.length; i += 1) {
    const j = i + 1
    const pos = coordsByIdx[j]
    if (!pos) continue
    const s = stops[i]
    const m = new AMap.Marker({
      position: pos,
      title: `${s.label} · ${s.order_sn}`,
      map: mapInstance,
    })
    const markHtml = escapeHtml(shortMapLabel(s.label))
    m.setLabel({
      direction: 'top',
      content: `<div class="chain-map-marker chain-map-marker--stop">${markHtml}</div>`,
      offset: new AMap.Pixel(0, -4),
    })
    overlays.push(m)
  }

  if (linePath.length >= 2) {
    const line = new AMap.Polyline({
      path: linePath,
      strokeColor: LINE_COLOR,
      strokeWeight: 5,
      strokeOpacity: 0.9,
      lineJoin: 'round',
      map: mapInstance,
    })
    overlays.push(line)
  }

  mapInstance.setFitView(overlays, false, [48, 48, 48, 48])
  setProgress(94, '渲染地图', '已绘制驾车路线，正在等待底图瓦片加载…')
  await nextTick()
  try {
    mapInstance.resize()
  } catch {
    /* ignore */
  }

  try {
    mapInstance.on('complete', onMapReady)
  } catch {
    /* 部分环境下无 complete 事件，走超时兜底 */
  }
  mapReadyFallbackTimer = window.setTimeout(onMapReady, 12000)
}

watch(
  () => ({
    ready: props.ready,
    depot: props.depotAddress,
    sig: (props.orders || []).map((o) => `${o.id}:${o.member_address}`).join('|'),
  }),
  () => {
    buildRoute()
  },
  /** 挂载时 ready 已为 true 时必须立即跑 buildRoute，否则会一直黑屏且无加载层 */
  { immediate: true, flush: 'post' },
)

onUnmounted(() => {
  destroyMap()
})
</script>

<style scoped>
.chain-map {
  position: relative;
  min-height: min(58vh, 480px);
}
.chain-map__err {
  padding: 12px 14px;
  border-radius: 8px;
  font-size: 13px;
  color: #fecaca;
  background: rgba(127, 29, 29, 0.25);
  border: 1px solid rgba(248, 113, 113, 0.35);
}
.chain-map__warn {
  position: relative;
  z-index: 3;
  margin: 0 0 8px;
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 12px;
  line-height: 1.5;
  color: #fde68a;
  background: rgba(120, 53, 15, 0.35);
  border: 1px solid rgba(251, 191, 36, 0.35);
}
.chain-map__idle {
  position: absolute;
  inset: 0;
  z-index: 3;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  text-align: center;
  font-size: 13px;
  line-height: 1.55;
  color: var(--sx-text-muted, #94a3b8);
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.88);
  border: 1px dashed rgba(148, 163, 184, 0.35);
  box-sizing: border-box;
}
.chain-map__loading {
  position: absolute;
  inset: 0;
  z-index: 4;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  font-size: 13px;
  color: var(--sx-text-readable-dim, #cbd5e1);
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.92);
  border: 1px solid rgba(94, 234, 212, 0.2);
  box-sizing: border-box;
}
.chain-map__loading-card {
  width: min(420px, 100%);
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 12px;
  text-align: center;
}
.chain-map__loading-icon {
  align-self: center;
  color: var(--sx-accent-cyan, #22d3ee);
}
.chain-map__loading-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--sx-text-title, #e2e8f0);
}
.chain-map__loading-detail {
  font-size: 12px;
  line-height: 1.5;
  color: var(--sx-text-muted, #94a3b8);
  word-break: break-word;
}
.chain-map__progress {
  width: 100%;
}
.chain-map__loading-hint {
  font-size: 11px;
  color: var(--sx-text-muted, #64748b);
}
.chain-map__canvas {
  width: 100%;
  height: min(58vh, 480px);
  border-radius: 10px;
  border: 1px solid rgba(94, 234, 212, 0.22);
  background: rgba(15, 23, 42, 0.5);
}
</style>

<style>
.chain-map-marker {
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 700;
  border: 1px solid rgba(148, 163, 184, 0.35);
  background: rgba(15, 23, 42, 0.92);
  color: #e2e8f0;
}
.chain-map-marker--depot {
  border-color: rgba(251, 191, 36, 0.55);
  color: #fcd34d;
}
.chain-map-marker--stop {
  border-color: rgba(56, 189, 248, 0.55);
  color: #7dd3fc;
  max-width: 168px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
