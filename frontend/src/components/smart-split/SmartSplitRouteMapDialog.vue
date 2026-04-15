<template>
  <el-dialog
    v-model="visible"
    title="智能排线"
    width="min(920px, 96vw)"
    class="split-route-dialog"
    append-to-body
    destroy-on-close
    @closed="onDialogClosed"
  >
    <p v-if="subtitle" class="split-route-dialog__sub">{{ subtitle }}</p>
    <div v-if="errorText" class="split-route-dialog__err">{{ errorText }}</div>
    <div v-show="!errorText" class="split-route-dialog__map-wrap">
      <div v-if="loading" class="split-route-dialog__loading" role="status">
        <el-icon class="is-loading" :size="22"><Loading /></el-icon>
        <span>正在地理编码并加载高德地图…</span>
      </div>
      <div ref="mapElRef" class="split-route-dialog__map" />
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { fetchAmapJsConfig, geocodeSmartSplitAddresses } from '../../api/governanceDemo.js'

const LINE_COLORS = ['#22d3ee', '#fbbf24', '#f472b6', '#a78bfa', '#34d399', '#fb923c']

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** 与确认分单 payload 结构一致，需含 customer_name、grouped */
  payload: { type: Object, default: null },
})

const emit = defineEmits(['update:modelValue'])

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const mapElRef = ref(null)
const loading = ref(false)
const errorText = ref('')
const subtitle = ref('')

let mapInstance = null
let amapScriptPromise = null

function collectSupplierByAddress(grouped) {
  const byAddr = new Map()
  for (const g of grouped || []) {
    const addr = String(g?.supplier_address || '').trim()
    if (!addr || addr === '—') continue
    const name = String(g?.supplier_name || '').trim()
    if (!byAddr.has(addr)) {
      byAddr.set(addr, { address: addr, names: [] })
    }
    const entry = byAddr.get(addr)
    if (name && !entry.names.includes(name)) entry.names.push(name)
  }
  return Array.from(byAddr.values())
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

function destroyMap() {
  if (mapInstance) {
    try {
      mapInstance.destroy()
    } catch {
      /* ignore */
    }
    mapInstance = null
  }
}

function onDialogClosed() {
  destroyMap()
  errorText.value = ''
  loading.value = false
  subtitle.value = ''
}

async function buildMap(payload) {
  errorText.value = ''
  subtitle.value = ''
  loading.value = true
  destroyMap()
  await nextTick()

  const customerAddr = String(payload?.customer_address || '').trim()
  const customerName = String(payload?.customer_name || '').trim()
  const customerQ = customerAddr || customerName
  const orderSn = String(payload?.order_sn || '').trim()
  const suppliers = collectSupplierByAddress(payload?.grouped)

  if (!suppliers.length) {
    loading.value = false
    errorText.value = '无有效供货方地址，无法排线。'
    ElMessage.warning(errorText.value)
    return
  }
  if (!customerQ || customerQ === '—') {
    loading.value = false
    errorText.value = '客户收货地址与客户名均为空，无法解析收货位置。'
    ElMessage.warning(errorText.value)
    return
  }

  let cfg
  try {
    cfg = await fetchAmapJsConfig()
  } catch (e) {
    loading.value = false
    errorText.value = typeof e === 'string' ? e : '获取地图配置失败'
    ElMessage.error(errorText.value)
    return
  }
  if (!cfg?.enabled || !cfg.key) {
    loading.value = false
    errorText.value = '服务端未配置高德 JSAPI（AMAP_JSAPI_KEY / AMAP_SECURITY_JSCODE）。'
    ElMessage.warning(errorText.value)
    return
  }

  const toGeocode = [...suppliers.map((s) => s.address), customerQ]
  const customerIndex = suppliers.length
  let geoRes
  try {
    geoRes = await geocodeSmartSplitAddresses({
      addresses: toGeocode,
      customer_index: customerIndex,
    })
  } catch (e) {
    loading.value = false
    const msg =
      typeof e === 'string'
        ? e
        : Array.isArray(e)
          ? e.map((x) => x?.msg || x).join('; ')
          : '地理编码失败'
    errorText.value = msg.includes('AMAP_WEB') ? `${msg}（智能排线需配置 Web 地理编码 Key）` : msg
    ElMessage.error(errorText.value)
    return
  }

  const results = Array.isArray(geoRes?.results) ? geoRes.results : []
  if (results.length !== toGeocode.length) {
    loading.value = false
    errorText.value = '地理编码结果异常，请重试。'
    ElMessage.error(errorText.value)
    return
  }

  const supplierCoords = []
  for (let i = 0; i < suppliers.length; i += 1) {
    const r = results[i]
    if (r?.lng == null || r?.lat == null) {
      loading.value = false
      errorText.value = `供货方地址无法定位：${suppliers[i].address}`
      ElMessage.warning(errorText.value)
      return
    }
    supplierCoords.push([Number(r.lng), Number(r.lat)])
  }
  const cust = results[results.length - 1]
  if (cust?.lng == null || cust?.lat == null) {
    loading.value = false
    errorText.value = `客户位置无法定位：${customerQ}（需 AMAP_WEB_KEY 与北京市域有效查询）`
    ElMessage.warning(errorText.value)
    return
  }
  const customerCoord = [Number(cust.lng), Number(cust.lat)]

  let AMap
  try {
    AMap = await loadAmapScript(cfg.key, cfg.securityJsCode)
  } catch (e) {
    loading.value = false
    errorText.value = typeof e === 'string' ? e : e?.message || '地图加载失败'
    ElMessage.error(errorText.value)
    return
  }

  if (!mapElRef.value) {
    loading.value = false
    errorText.value = '地图容器未就绪'
    return
  }

  mapInstance = new AMap.Map(mapElRef.value, {
    zoom: 11,
    viewMode: '2D',
    center: customerCoord,
  })

  const overlays = []
  const custTitle =
    customerAddr && customerName && customerAddr !== customerName
      ? `客户：${customerName} · ${customerAddr}`
      : `客户：${customerQ}`
  const custMarker = new AMap.Marker({
    position: customerCoord,
    title: custTitle,
    map: mapInstance,
  })
  custMarker.setLabel({
    direction: 'top',
    content: `<div class="split-route-marker split-route-marker--cust">客户</div>`,
    offset: new AMap.Pixel(0, -4),
  })
  overlays.push(custMarker)

  suppliers.forEach((s, idx) => {
    const pos = supplierCoords[idx]
    const labelText = s.names.length ? s.names.join('、') : '供货方'
    const m = new AMap.Marker({
      position: pos,
      title: `${labelText} · ${s.address}`,
      map: mapInstance,
    })
    m.setLabel({
      direction: 'top',
      content: `<div class="split-route-marker split-route-marker--sup">${labelText}</div>`,
      offset: new AMap.Pixel(0, -4),
    })
    overlays.push(m)

    const line = new AMap.Polyline({
      path: [pos, customerCoord],
      strokeColor: LINE_COLORS[idx % LINE_COLORS.length],
      strokeWeight: 4,
      strokeOpacity: 0.92,
      lineJoin: 'round',
      map: mapInstance,
    })
    overlays.push(line)
  })

  mapInstance.setFitView(overlays, false, [56, 56, 56, 56])
  loading.value = false
  subtitle.value = orderSn ? `订单 ${orderSn} · ${suppliers.length} 条供货线路（直线示意）` : `${suppliers.length} 条供货线路（直线示意）`
}

watch(
  () => props.modelValue,
  async (open) => {
    if (open && props.payload) {
      await nextTick()
      await nextTick()
      await buildMap(props.payload)
    }
  },
)
</script>

<style scoped>
.split-route-dialog__sub {
  margin: 0 0 10px;
  font-size: 12px;
  color: var(--sx-text-muted, #94a3b8);
  line-height: 1.5;
}
.split-route-dialog__err {
  padding: 12px 14px;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.5;
  color: #fecaca;
  background: rgba(127, 29, 29, 0.25);
  border: 1px solid rgba(248, 113, 113, 0.35);
  margin-bottom: 10px;
}
.split-route-dialog__map-wrap {
  position: relative;
}
.split-route-dialog__loading {
  position: absolute;
  inset: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 16px 12px;
  font-size: 13px;
  color: var(--sx-text-readable-dim, #cbd5e1);
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.82);
  backdrop-filter: blur(6px);
}
.split-route-dialog__map {
  width: 100%;
  height: min(62vh, 520px);
  border-radius: 10px;
  border: 1px solid rgba(94, 234, 212, 0.22);
  background: rgba(15, 23, 42, 0.6);
}
</style>

<style>
.split-route-dialog .el-dialog__body {
  padding-top: 8px;
}
.split-route-marker {
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  border: 1px solid rgba(148, 163, 184, 0.35);
  background: rgba(15, 23, 42, 0.92);
  color: #e2e8f0;
}
.split-route-marker--cust {
  border-color: rgba(52, 211, 153, 0.55);
  color: #6ee7b7;
}
.split-route-marker--sup {
  border-color: rgba(56, 189, 248, 0.5);
  color: #7dd3fc;
}
</style>
