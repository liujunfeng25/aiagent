<template>
  <div class="loc-page">
    <div class="vehicle-bar">
      <span><b>{{ plateno }}</b> — 设备位置 · 实时 / 历史（北斗）</span>
      <div>
        <el-button size="small" @click="$router.push('/logistics')">返回</el-button>
        <el-button size="small" @click="$router.push({ path: `/logistics/vehicle/${vehicleId}/bind`, query: { plateno } })">设备管理</el-button>
      </div>
    </div>

    <el-tabs v-model="mainTab">
      <el-tab-pane label="实时监控" name="rt">
        <div class="section-head">
          <span class="section-title">关键指标</span>
        </div>
        <el-row :gutter="12" class="cards" v-if="rtCard">
          <el-col :xs="12" :sm="8" :md="4" v-for="c in rtMetrics" :key="c.k">
            <el-card shadow="hover" class="metric">
              <div class="lbl">{{ c.label }}</div>
              <div class="val">{{ c.value }}</div>
            </el-card>
          </el-col>
        </el-row>
        <div v-else-if="rtError" class="hint err">{{ rtError }}</div>
        <div class="section-head section-head--map">
          <span class="section-title">实时位置</span>
        </div>
        <div ref="mapRtRef" class="map-box" />
        <div class="cam-block">
          <div class="section-head cam-head">
            <span class="section-title">车载摄像头</span>
            <el-button size="small" type="primary" @click="loadCamLive">刷新直播地址</el-button>
          </div>
          <div v-for="cam in camRows" :key="cam.camera_device_id" class="cam-card">
            <div class="cam-hd">
              <span>{{ cam.device_name }} · {{ cam.camera_source }}</span>
            </div>
            <p v-if="cam.error" class="err">{{ cam.error }}</p>
            <template v-else>
              <template v-if="cam.camera_source === 'ys7' && isEzopenUrl(cam.hls)">
                <p v-if="!cam.ys7_access_token" class="err">萤石播放缺少 accessToken，请点击「刷新直播地址」</p>
                <div v-else class="cam-video-wrap">
                  <div :id="ezContainerId(cam)" class="cam-ez" />
                </div>
              </template>
              <div v-else-if="isHttpUrl(cam.hls)" class="cam-video-wrap">
                <video class="cam-v" controls playsinline :src="cam.hls" />
              </div>
              <div v-else-if="cam.hls" class="ez">{{ cam.hls }}</div>
              <div v-if="cam.camera_source === 'ys7' && !cam.error" class="ptz">
                <span class="ptz-lbl">云台</span>
                <el-button-group>
                  <el-button size="small" @mousedown="ptzStart(cam, 0)" @mouseup="ptzStop(cam)" @touchstart.prevent="ptzStart(cam, 0)" @touchend.prevent="ptzStop(cam)">上</el-button>
                  <el-button size="small" @mousedown="ptzStart(cam, 1)" @mouseup="ptzStop(cam)">下</el-button>
                  <el-button size="small" @mousedown="ptzStart(cam, 2)" @mouseup="ptzStop(cam)">左</el-button>
                  <el-button size="small" @mousedown="ptzStart(cam, 3)" @mouseup="ptzStop(cam)">右</el-button>
                </el-button-group>
                <el-select v-model="ptzSpeed" size="small" style="width:80px;margin-left:8px">
                  <el-option :value="1" label="慢" />
                  <el-option :value="2" label="快" />
                </el-select>
              </div>
            </template>
          </div>
          <el-empty v-if="!camRows.length && !camLoading" description="无绑定摄像头或暂无地址" />
        </div>
      </el-tab-pane>

      <el-tab-pane label="历史轨迹" name="hi">
        <div class="history-toolbar sxw-hint">
          按本车在绑定页配置的北斗 macid / user_id 查询北斗定位历史轨迹（坐标已由服务端转为高德 GCJ-02）。
        </div>
        <el-form :inline="true" class="history-range-form">
          <el-form-item label="开始时间">
            <el-date-picker
              v-model="hist.start"
              type="datetime"
              value-format="YYYY-MM-DD HH:mm:ss"
              placeholder="选择开始时间"
              class="hist-dt-picker"
            />
          </el-form-item>
          <el-form-item label="结束时间">
            <el-date-picker
              v-model="hist.end"
              type="datetime"
              value-format="YYYY-MM-DD HH:mm:ss"
              placeholder="选择结束时间"
              class="hist-dt-picker"
            />
          </el-form-item>
          <el-form-item label="仅演示">
            <el-switch v-model="hist.forceDemo" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="histLoading" @click="loadHist">查询轨迹</el-button>
          </el-form-item>
        </el-form>
        <p v-if="hist.notice" class="hint">{{ hist.notice }}</p>
        <p v-if="hist.demoMsg" class="hint warn">{{ hist.demoMsg }}</p>
        <div class="section-head section-head--map">
          <span class="section-title">轨迹地图</span>
        </div>
        <div ref="mapHiRef" class="map-box map-box--history" />
        <!-- 与 sxw smart_logistics_bind/location.html #historyPlayback 一致：播放 / 暂停 / 重置 / 进度 / 时间 / 速度+逆地理 -->
        <div v-if="histPts.length" class="history-playback">
          <el-button size="small" type="primary" @click="onTrackPlay">播放</el-button>
          <el-button size="small" @click="onTrackPause">暂停</el-button>
          <el-button size="small" @click="onTrackReset">重置</el-button>
          <span class="history-playback-label">进度</span>
          <div class="track-progress-wrap">
            <el-slider
              v-model="playIdx"
              :min="0"
              :max="Math.max(0, histPts.length - 1)"
              :show-tooltip="true"
              @input="onTrackProgressUserInput"
              @change="onTrackProgressUserInput"
            />
          </div>
          <span class="track-time-label">{{ trackTimeLabel }}</span>
          <div class="history-playback-extra">
            <div>速度：<span>{{ trackSpeedText }}</span></div>
            <div class="playback-addr-row">地址：<span>{{ trackAddrText }}</span></div>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { sxwLogisticsAxiosParams } from '../utils/sxwLogisticsTenant'

const route = useRoute()
const vehicleId = computed(() => Number(route.params.id))
const plateno = computed(() => route.query.plateno || String(vehicleId.value))

const mainTab = ref('rt')
const mapRtRef = ref(null)
const mapHiRef = ref(null)
let mapRt = null
let mapHi = null
let mkRt = null
let polyHi = null
let mkPlay = null

const rtCard = ref(null)
const rtError = ref('')
const rtMetrics = computed(() => {
  const x = rtCard.value
  if (!x) return []
  return [
    { k: 't', label: '温度', value: x.temperature || '—' },
    { k: 'h', label: '湿度', value: x.humidity || '—' },
    { k: 's', label: '速度', value: x.speed != null ? `${x.speed} km/h` : '—' },
    { k: 'p', label: '电量', value: x.power || '—' },
    { k: 'tm', label: '时间', value: x.lastDataTime || '—' },
  ]
})

const camRows = ref([])
const camLoading = ref(false)
const ptzSpeed = ref(1)

const hist = reactive({ start: '', end: '', forceDemo: false, notice: '', demoMsg: '' })
const histPts = ref([])
const histLoading = ref(false)
const playIdx = ref(0)

/** sxw location.html：逆地理缓存 */
const historyGeocodeCache = {}
let historyGeocoder = null
let playTimer = null
const PLAY_SPEED_MS = 320

const trackTimeLabel = ref('—')
const trackSpeedText = ref('—')
const trackAddrText = ref('—')

function isHttpUrl(u) {
  if (!u || typeof u !== 'string') return false
  const s = u.trim().toLowerCase()
  return s.startsWith('http://') || s.startsWith('https://')
}

function isEzopenUrl(u) {
  if (!u || typeof u !== 'string') return false
  return u.trim().toLowerCase().startsWith('ezopen://')
}

function ezContainerId(cam) {
  return `ys7-ez-${cam.camera_device_id}`
}

const ys7EzPlayers = new Map()
let ezUIKitScriptPromise = null

function ensureEzUIKitScript() {
  if (window.EZUIKit && window.EZUIKit.EZUIKitPlayer) {
    return Promise.resolve()
  }
  if (!ezUIKitScriptPromise) {
    ezUIKitScriptPromise = new Promise((resolve, reject) => {
      const s = document.createElement('script')
      s.src = 'https://cdn.jsdelivr.net/npm/ezuikit-js@8.2.6/ezuikit.js'
      s.async = true
      s.onload = () => resolve()
      s.onerror = () => reject(new Error('ezuikit'))
      document.head.appendChild(s)
    })
  }
  return ezUIKitScriptPromise
}

function destroyYs7EzPlayer(cameraDeviceId) {
  const p = ys7EzPlayers.get(cameraDeviceId)
  if (!p) return
  try {
    if (typeof p.destroy === 'function') p.destroy()
  } catch (_) { /* ignore */ }
  try {
    if (typeof p.stop === 'function') p.stop()
  } catch (_) { /* ignore */ }
  ys7EzPlayers.delete(cameraDeviceId)
}

function destroyAllYs7EzPlayers() {
  for (const id of [...ys7EzPlayers.keys()]) {
    destroyYs7EzPlayer(id)
  }
}

async function syncYs7EzUIKitPlayers() {
  await nextTick()
  const cams = camRows.value || []
  const keep = new Set()
  for (const cam of cams) {
    if (cam.error || cam.camera_source !== 'ys7' || !isEzopenUrl(cam.hls) || !cam.ys7_access_token) {
      continue
    }
    keep.add(cam.camera_device_id)
    const elId = ezContainerId(cam)
    const el = document.getElementById(elId)
    if (!el) continue
    destroyYs7EzPlayer(cam.camera_device_id)
    try {
      await ensureEzUIKitScript()
      const w = Math.max(320, el.clientWidth || 640)
      const h = Math.max(280, Math.floor((w * 9) / 16))
      const player = new window.EZUIKit.EZUIKitPlayer({
        id: elId,
        accessToken: cam.ys7_access_token,
        url: cam.hls.trim(),
        width: w,
        height: h,
      })
      ys7EzPlayers.set(cam.camera_device_id, player)
    } catch (e) {
      ElMessage.error('萤石 EZUIKit 加载失败，请检查网络或稍后刷新')
    }
  }
  for (const id of [...ys7EzPlayers.keys()]) {
    if (!keep.has(id)) destroyYs7EzPlayer(id)
  }
}

watch(camRows, () => {
  syncYs7EzUIKitPlayers()
}, { deep: true, flush: 'post' })

onMounted(async () => {
  await initMapRt()
  loadRealtime()
})

onUnmounted(() => {
  stopTrackPlay()
  destroyAllYs7EzPlayers()
  if (mapRt) mapRt.destroy()
  if (mapHi) mapHi.destroy()
})

watch(mainTab, async (t) => {
  if (t === 'hi' && !mapHi) {
    await initMapHi()
  }
})

async function initMapRt() {
  const { data } = await axios.get('/api/logistics/amap-config')
  const cfg = data.data || data
  const { key, securityJsCode } = cfg
  if (!key) {
    ElMessage.warning('未配置高德 Key')
    return
  }
  window._AMapSecurityConfig = { securityJsCode }
  await loadScript(`https://webapi.amap.com/maps?v=2.0&key=${key}`)
  mapRt = new window.AMap.Map(mapRtRef.value, {
    zoom: 13,
    center: [116.397428, 39.90923],
  })
}

async function initMapHi() {
  if (!window.AMap) return
  await new Promise((r) => setTimeout(r, 50))
  mapHi = new window.AMap.Map(mapHiRef.value, {
    zoom: 12,
    center: [116.397428, 39.90923],
  })
}

function loadScript(src) {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) { resolve(); return }
    const s = document.createElement('script')
    s.src = src
    s.onload = resolve
    s.onerror = reject
    document.head.appendChild(s)
  })
}

async function loadRealtime() {
  rtError.value = ''
  rtCard.value = null
  try {
    const { data } = await axios.get(`/api/logistics/vehicles/${vehicleId.value}/realtime-sxw`, {
      params: sxwLogisticsAxiosParams(),
    })
    if (data.status && data.status !== 200) {
      rtError.value = typeof data.data === 'string' ? data.data : '无实时数据'
      return
    }
    const row = (data.data && data.data[0]) || null
    if (!row) {
      rtError.value = '无数据'
      return
    }
    rtCard.value = row
    const lng = parseFloat(row.longitude)
    const lat = parseFloat(row.latitude)
    if (mapRt && lng && lat) {
      if (mkRt) mapRt.remove(mkRt)
      mkRt = new window.AMap.Marker({ position: [lng, lat] })
      mapRt.add(mkRt)
      mapRt.setCenter([lng, lat])
    }
  } catch (e) {
    rtError.value = e.response?.data?.detail || e.message || '加载失败'
  }
  loadCamLive()
}

async function loadCamLive() {
  camLoading.value = true
  try {
    const { data } = await axios.get(`/api/logistics/vehicles/${vehicleId.value}/cameras/live`, {
      params: sxwLogisticsAxiosParams(),
    })
    if (data.status && data.status !== 200) {
      camRows.value = []
      return
    }
    camRows.value = data.data || []
  } finally {
    camLoading.value = false
  }
}

let _ptzCam = null
async function ptzStart(cam, direction) {
  _ptzCam = cam
  try {
    const { data } = await axios.post(
      '/api/logistics/sxw/cameras/ptz',
      {
        vehicle_id: vehicleId.value,
        camera_device_id: cam.camera_device_id,
        op: 'start',
        direction,
        speed: ptzSpeed.value,
      },
      { params: sxwLogisticsAxiosParams() },
    )
    if (data.status !== 200) ElMessage.error(data.data || '云台失败')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '云台请求失败')
  }
}

async function ptzStop(cam) {
  const c = cam || _ptzCam
  if (!c) return
  try {
    await axios.post(
      '/api/logistics/sxw/cameras/ptz',
      {
        vehicle_id: vehicleId.value,
        camera_device_id: c.camera_device_id,
        op: 'stop',
        direction: 0,
        speed: 1,
      },
      { params: sxwLogisticsAxiosParams() },
    )
  } catch (_) { /* ignore */ }
}

function toUnixSec(isoLocal) {
  if (!isoLocal) return 0
  const [d, t] = isoLocal.split(' ')
  const [y, m, day] = d.split('-').map(Number)
  const [hh, mm, ss] = t.split(':').map(Number)
  return Math.floor(new Date(y, m - 1, day, hh, mm, ss).getTime() / 1000)
}

function stopTrackPlay() {
  if (playTimer) {
    clearInterval(playTimer)
    playTimer = null
  }
}

/** sxw formatTs */
function formatTrackTs(sec) {
  if (sec == null || sec === '') return '—'
  const d = new Date(Number(sec) * 1000)
  if (Number.isNaN(d.getTime())) return '—'
  const z = (n) => (n < 10 ? `0${n}` : `${n}`)
  return `${d.getFullYear()}/${z(d.getMonth() + 1)}/${z(d.getDate())} ${z(d.getHours())}:${z(d.getMinutes())}:${z(d.getSeconds())}`
}

function ensureHistoryGeocoder(cb) {
  if (!window.AMap) {
    cb(null)
    return
  }
  if (historyGeocoder) {
    cb(historyGeocoder)
    return
  }
  window.AMap.plugin('AMap.Geocoder', () => {
    try {
      historyGeocoder = new window.AMap.Geocoder({ radius: 1000 })
    } catch (_) {
      historyGeocoder = null
    }
    cb(historyGeocoder)
  })
}

/** sxw setTrackIndex：进度、速度、逆地理（含 cache） */
function setTrackIndex(idx) {
  const pts = histPts.value
  if (!pts.length) return
  const max = pts.length - 1
  const i = Math.max(0, Math.min(Number(idx) || 0, max))
  playIdx.value = i
  const meta = pts[i] || {}
  if (mkPlay && mapHi) {
    mkPlay.setPosition([meta.lng, meta.lat])
  }
  trackTimeLabel.value = formatTrackTs(meta.monitorTime)
  const sp = meta.speed != null && String(meta.speed) !== '' ? String(meta.speed) : '—'
  trackSpeedText.value = sp

  const lng = meta.lng
  const lat = meta.lat
  if (lng == null || lat == null || Number.isNaN(parseFloat(lng)) || Number.isNaN(parseFloat(lat))) {
    trackAddrText.value = '—'
    return
  }
  const lk = `${lng},${lat}`
  if (historyGeocodeCache[lk]) {
    trackAddrText.value = historyGeocodeCache[lk]
    return
  }
  trackAddrText.value = '解析中…'
  const idxSnapshot = i
  ensureHistoryGeocoder((geocoder) => {
    if (!geocoder) {
      trackAddrText.value = '—'
      return
    }
    if (historyGeocodeCache[lk]) {
      trackAddrText.value = historyGeocodeCache[lk]
      return
    }
    geocoder.getAddress([parseFloat(lng), parseFloat(lat)], (status, result) => {
      let addr = '—'
      if (status === 'complete' && result?.regeocode) {
        addr = result.regeocode.formattedAddress || result.regeocode.address || '—'
      }
      historyGeocodeCache[lk] = addr
      if (playIdx.value === idxSnapshot) {
        trackAddrText.value = addr
      }
    })
  })
}

function onTrackPlay() {
  if (!histPts.value.length) return
  stopTrackPlay()
  playTimer = setInterval(() => {
    if (playIdx.value >= histPts.value.length - 1) {
      stopTrackPlay()
      return
    }
    setTrackIndex(playIdx.value + 1)
  }, PLAY_SPEED_MS)
}

function onTrackPause() {
  stopTrackPlay()
}

function onTrackReset() {
  stopTrackPlay()
  setTrackIndex(0)
}

function onTrackProgressUserInput(val) {
  stopTrackPlay()
  const i = val !== undefined && val !== null ? Number(val) : playIdx.value
  setTrackIndex(i)
}

async function loadHist() {
  if (!hist.start || !hist.end) {
    ElMessage.warning('请选择时间范围')
    return
  }
  histLoading.value = true
  stopTrackPlay()
  hist.notice = ''
  hist.demoMsg = ''
  histPts.value = []
  trackTimeLabel.value = '—'
  trackSpeedText.value = '—'
  trackAddrText.value = '—'
  try {
    const st = toUnixSec(hist.start)
    const et = toUnixSec(hist.end)
    const { data } = await axios.post(
      `/api/logistics/vehicles/${vehicleId.value}/track-sxw`,
      { start_time: st, end_time: et, force_demo: hist.forceDemo },
      { params: sxwLogisticsAxiosParams() },
    )
    if (data.status !== 200) {
      ElMessage.error(typeof data.data === 'string' ? data.data : '查询失败')
      return
    }
    const payload = data.data || {}
    histPts.value = payload.points || []
    hist.notice = payload.notice || ''
    hist.demoMsg = payload.message || ''
    if (!mapHi) await initMapHi()
    drawHist()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message || '查询失败')
  } finally {
    histLoading.value = false
  }
}

function drawHist() {
  if (!mapHi || !histPts.value.length) return
  stopTrackPlay()
  if (polyHi) mapHi.remove(polyHi)
  if (mkPlay) mapHi.remove(mkPlay)
  const path = histPts.value.map((p) => [p.lng, p.lat])
  polyHi = new window.AMap.Polyline({
    path,
    strokeColor: '#1a73e8',
    strokeWeight: 5,
    lineJoin: 'round',
  })
  mapHi.add(polyHi)
  mkPlay = new window.AMap.Marker({
    position: path[0],
    map: mapHi,
    title: '轨迹回放',
  })
  mapHi.setFitView([polyHi])
  setTrackIndex(0)
}
</script>

<style scoped>
.loc-page {
  width: 100%;
  max-width: min(1480px, calc(100vw - 48px));
  margin: 0 auto;
  padding: 24px clamp(16px, 2.5vw, 28px) 36px;
  background: linear-gradient(180deg, #f6f8fc 0%, #eef1f6 48%, #f4f6f9 100%);
  min-height: calc(100vh - 56px);
  box-sizing: border-box;
}
.vehicle-bar {
  background: linear-gradient(125deg, #1e293b 0%, #334155 55%, #263445 100%);
  color: #f1f5f9;
  padding: 14px 20px;
  border-radius: 12px;
  margin-bottom: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08), 0 8px 24px rgba(15, 23, 42, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.1);
}
.vehicle-bar > div:last-child {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-left: auto;
}
.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 20px 0 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(15, 23, 42, 0.1);
}
.section-head:first-of-type {
  margin-top: 4px;
}
.section-head--map {
  margin-top: 24px;
}
.section-title {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #64748b;
}
.cards {
  margin-bottom: 4px;
}
.cards :deep(.el-card) {
  border-radius: 12px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.06);
  transition: box-shadow 0.2s ease, transform 0.2s ease;
}
.cards :deep(.el-card:hover) {
  box-shadow: 0 6px 20px rgba(15, 23, 42, 0.1);
}
.metric :deep(.el-card__body) {
  padding: 16px 18px;
}
.metric .lbl {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #94a3b8;
}
.metric .val {
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
  margin-top: 8px;
  line-height: 1.25;
  font-variant-numeric: tabular-nums;
}
.map-box {
  width: 100%;
  min-height: 420px;
  height: clamp(380px, 52vh, 520px);
  border-radius: 12px;
  margin: 0 0 4px;
  border: 1px solid rgba(15, 23, 42, 0.1);
  box-shadow: 0 2px 16px rgba(15, 23, 42, 0.07);
  overflow: hidden;
  background: #e2e8f0;
}
/* sxw #mapHistory：固定 400px 高 */
.map-box--history {
  height: 400px;
  min-height: 400px;
}
.history-toolbar.sxw-hint {
  font-size: 12px;
  color: #475569;
  line-height: 1.5;
  margin-bottom: 10px;
}

/* 历史轨迹：时间范围在全局暗色主题下对比度不足，此处强制浅色高对比 */
.history-range-form {
  background: #ffffff;
  padding: 14px 16px;
  border-radius: 10px;
  border: 1px solid rgba(15, 23, 42, 0.12);
  margin-bottom: 12px;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.06);
  align-items: center;
  flex-wrap: wrap;
  gap: 4px 0;
}

.loc-page :deep(.history-range-form .el-form-item) {
  margin-bottom: 8px;
  margin-right: 16px;
}

.loc-page :deep(.history-range-form .el-form-item__label) {
  color: #0f172a;
  font-weight: 600;
  font-size: 13px;
}

.loc-page :deep(.history-range-form .hist-dt-picker) {
  width: 208px;
  max-width: 100%;
}

.loc-page :deep(.history-range-form .hist-dt-picker .el-input__wrapper) {
  background-color: #f8fafc;
  box-shadow: 0 0 0 1px #94a3b8 inset;
}

.loc-page :deep(.history-range-form .hist-dt-picker .el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px #64748b inset;
}

.loc-page :deep(.history-range-form .hist-dt-picker .el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px #2563eb inset, 0 0 0 3px rgba(37, 99, 235, 0.2);
}

.loc-page :deep(.history-range-form .hist-dt-picker .el-input__inner) {
  color: #0f172a;
  font-size: 13px;
  -webkit-text-fill-color: #0f172a;
}

.loc-page :deep(.history-range-form .hist-dt-picker .el-input__prefix-inner .el-icon) {
  color: #475569;
}
/* sxw .history-playback / .history-playback-extra */
.history-playback {
  display: flex;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 10px;
  background: #fff;
  border-radius: 10px;
  padding: 12px 14px;
  margin-top: 12px;
  margin-bottom: 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  border: 1px solid rgba(15, 23, 42, 0.06);
}
.history-playback-label {
  margin: 0 6px 0 0;
  color: #666;
  font-size: 13px;
  line-height: 32px;
}
.track-progress-wrap {
  flex: 1;
  min-width: 120px;
  max-width: 400px;
  align-self: center;
  padding: 0 4px;
}
.track-progress-wrap :deep(.el-slider) {
  width: 100%;
}
.track-time-label {
  color: #666;
  font-size: 12px;
  white-space: nowrap;
  line-height: 32px;
}
.history-playback-extra {
  flex: 1;
  min-width: 200px;
  max-width: 420px;
  margin-left: 4px;
  font-size: 12px;
  line-height: 1.45;
  color: #333;
}
.playback-addr-row {
  margin-top: 4px;
  color: #555;
}
.cam-block {
  margin-top: 8px;
}
.cam-block .section-head {
  margin-top: 8px;
}
.cam-card {
  background: #fff;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 12px;
  padding: 16px 18px;
  margin-bottom: 16px;
  box-shadow: 0 2px 14px rgba(15, 23, 42, 0.05);
}
.cam-hd {
  margin-bottom: 12px;
  font-weight: 600;
  font-size: 14px;
  color: #334155;
}
.cam-video-wrap {
  position: relative;
  width: 100%;
  padding-bottom: 56.25%;
  border-radius: 10px;
  overflow: hidden;
  background: #0a0a0a;
  border: 1px solid rgba(15, 23, 42, 0.2);
}
.cam-video-wrap .cam-v,
.cam-video-wrap .cam-ez {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  min-height: 0;
  border-radius: 0;
}
.cam-v {
  object-fit: contain;
  background: #000;
}
.cam-ez {
  background: #000;
}
.ptz {
  margin-top: 14px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.ptz-lbl {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #64748b;
  margin-right: 4px;
}
.err {
  color: #dc2626;
}
.hint {
  font-size: 13px;
  color: #475569;
  margin: 10px 0;
}
.hint.warn {
  color: #b45309;
}
.ez {
  font-size: 12px;
  font-family: ui-monospace, monospace;
  word-break: break-all;
  color: #475569;
  padding: 10px 12px;
  margin-top: 4px;
  border-left: 3px solid #cbd5e1;
  background: rgba(248, 250, 252, 0.95);
  border-radius: 0 8px 8px 0;
  line-height: 1.5;
}

.loc-page :deep(.el-tabs__header) {
  margin-bottom: 8px;
}
.loc-page :deep(.el-tabs__nav-wrap::after) {
  height: 1px;
  background-color: rgba(15, 23, 42, 0.08);
}
</style>
