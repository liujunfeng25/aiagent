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
        <div v-if="rtCard" class="cards-grid">
          <div v-for="c in rtMetrics" :key="c.k" class="metric-card">
            <div class="metric-card__label">{{ c.label }}</div>
            <div class="metric-card__value">{{ c.value }}</div>
            <p class="metric-card__desc">{{ c.desc }}</p>
            <div class="metric-card__delta">
              <span class="metric-card__delta-lbl">{{ c.deltaLabel }}</span>
              <span class="metric-card__delta-val">{{ c.delta }}</span>
            </div>
          </div>
        </div>
        <div v-else-if="rtError" class="hint err">{{ rtError }}</div>
        <div class="section-head section-head--map">
          <div class="section-head__title-wrap">
            <span class="section-title">实时位置</span>
            <p class="sxw-hint sxw-hint--inline">
              与食迅 <code class="sxw-hint__code">location.html</code> 一致：<strong>不在此页做坐标换算</strong>；实时经纬度已由后端按
              <code class="sxw-hint__code">Gps18Api::lngLatToAmapGcj02</code> 同源逻辑转为高德 GCJ-02。
              若你直连未转换的原始点，可调试 <code class="sxw-hint__code">?rtCoord=wgs</code> 或 <code class="sxw-hint__code">?rtCoord=bd09</code>。
            </p>
          </div>
          <el-button size="small" type="primary" :loading="camLoading" @click="loadCamLive">刷新直播地址</el-button>
        </div>
        <div class="rt-map-cam">
          <div class="rt-map-cam__map">
            <div ref="mapRtRef" class="map-box map-box--rt" />
          </div>
          <aside class="rt-map-cam__cams" aria-label="车载摄像头">
            <p v-if="camOverflowCount > 0" class="cam-overflow-hint">
              已绑定 {{ camRows.length }} 路，此处固定展示前 {{ CAM_SLOT_COUNT }} 路
            </p>
            <div
              v-for="slot in camSlots"
              :key="slot.i"
              class="cam-slot"
            >
              <div class="cam-slot__hd">
                <span>摄像头 {{ slot.i + 1 }}</span>
                <span v-if="slot.cam" class="cam-slot__meta">{{ slot.cam.device_name || slot.cam.camera_source }}</span>
              </div>
              <template v-if="slot.cam">
                <div class="cam-slot__body">
                  <p v-if="slot.cam.error" class="err">{{ slot.cam.error }}</p>
                  <template v-else>
                    <div class="cam-slot__actions">
                      <el-button size="small" type="primary" link @click="openCamLightbox(slot.cam)">
                        放大播放
                      </el-button>
                    </div>
                    <template v-if="slot.cam.camera_source === 'ys7' && isEzopenUrl(slot.cam.hls)">
                      <p v-if="!slot.cam.ys7_access_token" class="err">萤石播放缺少 accessToken，请点击「刷新直播地址」</p>
                      <div v-else class="cam-video-wrap cam-video-wrap--slot">
                        <div :id="ezContainerId(slot.cam)" class="cam-ez" />
                      </div>
                    </template>
                    <div v-else-if="isHttpUrl(slot.cam.hls)" class="cam-video-wrap cam-video-wrap--slot">
                      <video class="cam-v" controls playsinline :src="slot.cam.hls" />
                    </div>
                    <div v-else-if="slot.cam.hls" class="ez ez--compact">{{ slot.cam.hls }}</div>
                    <div v-if="slot.cam.camera_source === 'ys7' && !slot.cam.error" class="ptz ptz--compact">
                      <span class="ptz-lbl">云台</span>
                      <el-button-group>
                        <el-button size="small" @mousedown="ptzStart(slot.cam, 0)" @mouseup="ptzStop(slot.cam)" @touchstart.prevent="ptzStart(slot.cam, 0)" @touchend.prevent="ptzStop(slot.cam)">上</el-button>
                        <el-button size="small" @mousedown="ptzStart(slot.cam, 1)" @mouseup="ptzStop(slot.cam)">下</el-button>
                        <el-button size="small" @mousedown="ptzStart(slot.cam, 2)" @mouseup="ptzStop(slot.cam)">左</el-button>
                        <el-button size="small" @mousedown="ptzStart(slot.cam, 3)" @mouseup="ptzStop(slot.cam)">右</el-button>
                      </el-button-group>
                      <el-select v-model="ptzSpeed" size="small" class="ptz-speed">
                        <el-option :value="1" label="慢" />
                        <el-option :value="2" label="快" />
                      </el-select>
                    </div>
                  </template>
                </div>
              </template>
              <div v-else class="cam-placeholder">
                <span class="cam-placeholder__title">暂无视频流</span>
                <span class="cam-placeholder__sub">硬件接入后自动占用此位</span>
              </div>
            </div>
          </aside>
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

    <el-dialog
      v-model="camDialogOpen"
      class="cam-lightbox-dialog"
      width="min(960px, 94vw)"
      align-center
      destroy-on-close
      :close-on-click-modal="true"
      @closed="onCamDialogClosed"
    >
      <template #header>
        <span class="cam-lightbox-title">实时画面 · {{ camDialogCam?.device_name || '摄像头' }}</span>
      </template>
      <div v-if="camDialogCam" class="cam-lightbox-body">
        <p v-if="camDialogCam.error" class="err">{{ camDialogCam.error }}</p>
        <template v-else>
          <template v-if="camDialogCam.camera_source === 'ys7' && isEzopenUrl(camDialogCam.hls)">
            <p v-if="!camDialogCam.ys7_access_token" class="err">萤石播放缺少 accessToken，请关闭后点击「刷新直播地址」</p>
            <div v-else class="cam-video-wrap cam-video-wrap--lightbox">
              <div :id="ezContainerIdDialog(camDialogCam)" class="cam-ez" />
            </div>
          </template>
          <div v-else-if="isHttpUrl(camDialogCam.hls)" class="cam-video-wrap cam-video-wrap--lightbox">
            <video class="cam-v" controls playsinline :src="camDialogCam.hls" />
          </div>
          <div v-else-if="camDialogCam.hls" class="ez">{{ camDialogCam.hls }}</div>
          <div v-if="camDialogCam.camera_source === 'ys7' && !camDialogCam.error" class="ptz">
            <span class="ptz-lbl">云台</span>
            <el-button-group>
              <el-button size="small" @mousedown="ptzStart(camDialogCam, 0)" @mouseup="ptzStop(camDialogCam)" @touchstart.prevent="ptzStart(camDialogCam, 0)" @touchend.prevent="ptzStop(camDialogCam)">上</el-button>
              <el-button size="small" @mousedown="ptzStart(camDialogCam, 1)" @mouseup="ptzStop(camDialogCam)">下</el-button>
              <el-button size="small" @mousedown="ptzStart(camDialogCam, 2)" @mouseup="ptzStop(camDialogCam)">左</el-button>
              <el-button size="small" @mousedown="ptzStart(camDialogCam, 3)" @mouseup="ptzStop(camDialogCam)">右</el-button>
            </el-button-group>
            <el-select v-model="ptzSpeed" size="small" class="ptz-speed-dialog">
              <el-option :value="1" label="慢" />
              <el-option :value="2" label="快" />
            </el-select>
          </div>
        </template>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { sxwLogisticsAxiosParams } from '../utils/sxwLogisticsTenant'
import { wgs84ToGcj02, bd09ToGcj02 } from '../utils/chinaCoordTransform'

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

const CAM_SLOT_COUNT = 3

const rtCard = ref(null)
const rtError = ref('')
const rtMetrics = computed(() => {
  const x = rtCard.value
  if (!x) return []
  return [
    {
      k: 't',
      label: '温度',
      value: x.temperature != null && x.temperature !== '' ? String(x.temperature) : '—',
      desc: '车厢温度 ·℃',
      deltaLabel: '较上一包',
      delta: '—',
    },
    {
      k: 'h',
      label: '湿度',
      value: x.humidity != null && x.humidity !== '' ? String(x.humidity) : '—',
      desc: '相对湿度 · %RH',
      deltaLabel: '较上一包',
      delta: '—',
    },
    {
      k: 's',
      label: '速度',
      value: x.speed != null && x.speed !== '' ? `${x.speed} km/h` : '—',
      desc: 'GNSS / 终端推算',
      deltaLabel: '较上一包',
      delta: '—',
    },
    {
      k: 'p',
      label: '电量',
      value: x.power != null && x.power !== '' ? String(x.power) : '—',
      desc: '车载电压 · 演示字段',
      deltaLabel: '较上一包',
      delta: '—',
    },
    {
      k: 'tm',
      label: '时间',
      value: x.lastDataTime || '—',
      desc: '北斗 / 平台上报时刻',
      deltaLabel: '环比口径',
      delta: '待统计',
    },
  ]
})

const camRows = ref([])
const camLoading = ref(false)
const ptzSpeed = ref(1)

/** 居中放大播放（萤石单实例：弹窗打开时销毁侧栏同路播放器，关闭后恢复） */
const camDialogOpen = ref(false)
const camDialogCam = ref(null)

const camSlots = computed(() => {
  const rows = camRows.value || []
  return Array.from({ length: CAM_SLOT_COUNT }, (_, i) => ({
    i,
    cam: rows[i] || null,
  }))
})

const camOverflowCount = computed(() => Math.max(0, (camRows.value?.length || 0) - CAM_SLOT_COUNT))

function resizeRtMap() {
  if (mapRt && typeof mapRt.resize === 'function') {
    try {
      mapRt.resize()
    } catch (_) { /* ignore */ }
  }
}

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

function ezContainerIdDialog(cam) {
  return `ys7-ez-dialog-${cam.camera_device_id}`
}

function openCamLightbox(cam) {
  if (!cam || cam.error) return
  if (cam.camera_source === 'ys7' && isEzopenUrl(cam.hls) && !cam.ys7_access_token) {
    ElMessage.warning('请先点击「刷新直播地址」获取播放凭证')
    return
  }
  if (cam.camera_source === 'ys7' && isEzopenUrl(cam.hls) && cam.ys7_access_token) {
    destroyYs7EzPlayer(cam.camera_device_id)
  }
  camDialogCam.value = cam
  camDialogOpen.value = true
}

function onCamDialogClosed() {
  const cam = camDialogCam.value
  if (cam && cam.camera_source === 'ys7' && isEzopenUrl(cam.hls) && cam.ys7_access_token) {
    destroyYs7EzPlayer(cam.camera_device_id)
  }
  camDialogCam.value = null
  nextTick(() => syncYs7EzUIKitPlayers())
}

watch(camDialogOpen, async (open) => {
  if (!open) return
  await nextTick()
  await syncYs7DialogPlayer()
})

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

async function syncYs7DialogPlayer() {
  const cam = camDialogCam.value
  if (!camDialogOpen.value || !cam || cam.error) return
  if (cam.camera_source !== 'ys7' || !isEzopenUrl(cam.hls) || !cam.ys7_access_token) return
  await nextTick()
  const elId = ezContainerIdDialog(cam)
  const el = document.getElementById(elId)
  if (!el) return
  destroyYs7EzPlayer(cam.camera_device_id)
  try {
    await ensureEzUIKitScript()
    const wrap = el.closest('.cam-video-wrap--lightbox')
    const w = Math.max(640, wrap?.clientWidth || el.clientWidth || 880)
    const h = Math.max(360, Math.floor((w * 9) / 16))
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

async function syncYs7EzUIKitPlayers() {
  await nextTick()
  const cams = camRows.value || []
  const keep = new Set()
  for (const cam of cams) {
    if (cam.error || cam.camera_source !== 'ys7' || !isEzopenUrl(cam.hls) || !cam.ys7_access_token) {
      continue
    }
    if (
      camDialogOpen.value
      && camDialogCam.value
      && cam.camera_device_id === camDialogCam.value.camera_device_id
    ) {
      continue
    }
    keep.add(cam.camera_device_id)
    const elId = ezContainerId(cam)
    const el = document.getElementById(elId)
    if (!el) continue
    destroyYs7EzPlayer(cam.camera_device_id)
    try {
      await ensureEzUIKitScript()
      const w = Math.max(160, el.clientWidth || 280)
      let h = Math.floor((w * 9) / 16)
      h = Math.min(h, 200)
      h = Math.max(h, 72)
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
  if (camDialogOpen.value && camDialogCam.value?.camera_device_id != null) {
    keep.add(camDialogCam.value.camera_device_id)
  }
  for (const id of [...ys7EzPlayers.keys()]) {
    if (!keep.has(id)) destroyYs7EzPlayer(id)
  }
}

watch(camRows, () => {
  syncYs7EzUIKitPlayers()
}, { deep: true, flush: 'post' })

watch(camRows, async () => {
  await nextTick()
  resizeRtMap()
}, { deep: true })

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
  await nextTick()
  resizeRtMap()
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
    let lng = parseFloat(row.longitude)
    let lat = parseFloat(row.latitude)
    if (mapRt && Number.isFinite(lng) && Number.isFinite(lat)) {
      /* 默认与 sxw 一致：realtime-sxw 已在服务端 _lng_lat_to_amap_gcj02 转出 GCJ-02，禁止二次转换 */
      const mode = String(route.query.rtCoord || '').toLowerCase()
      if (mode === 'wgs' || mode === 'gps') {
        ;[lng, lat] = wgs84ToGcj02(lng, lat)
      } else if (mode === 'bd09' || mode === 'baidu') {
        ;[lng, lat] = bd09ToGcj02(lng, lat)
      }
      if (mkRt) mapRt.remove(mkRt)
      mkRt = new window.AMap.Marker({ position: [lng, lat] })
      mapRt.add(mkRt)
      mapRt.setCenter([lng, lat])
    }
    await nextTick()
    resizeRtMap()
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
.section-head__title-wrap {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  min-width: 0;
  flex: 1;
}
.sxw-hint--inline {
  margin: 0;
  font-size: 12px;
  line-height: 1.45;
  color: #64748b;
  max-width: 56rem;
}
.sxw-hint__code {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  background: rgba(15, 23, 42, 0.06);
  color: #0f172a;
}
.section-title {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #64748b;
}
.cards-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
  margin-bottom: 8px;
}
@media (max-width: 1200px) {
  .cards-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}
@media (max-width: 640px) {
  .cards-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
.metric-card {
  background: #fff;
  border-radius: 12px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.06);
  padding: 14px 16px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 118px;
  transition: box-shadow 0.2s ease;
}
.metric-card:hover {
  box-shadow: 0 6px 20px rgba(15, 23, 42, 0.1);
}
.metric-card__label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #64748b;
}
.metric-card__value {
  font-size: clamp(18px, 2.2vw, 22px);
  font-weight: 700;
  color: #0f172a;
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
}
.metric-card__desc {
  margin: 0;
  font-size: 11px;
  line-height: 1.35;
  color: #64748b;
}
.metric-card__delta {
  margin-top: auto;
  padding-top: 8px;
  border-top: 1px solid rgba(15, 23, 42, 0.06);
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  font-size: 11px;
}
.metric-card__delta-lbl {
  color: #94a3b8;
  flex-shrink: 0;
}
.metric-card__delta-val {
  color: #475569;
  font-variant-numeric: tabular-nums;
  text-align: right;
}

.rt-map-cam {
  display: flex;
  gap: 16px;
  align-items: stretch;
  margin-bottom: 8px;
  min-height: clamp(400px, 52vh, 560px);
}
.rt-map-cam__map {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.rt-map-cam__cams {
  flex: 0 0 min(300px, 30vw);
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 260px;
}
.cam-overflow-hint {
  margin: 0;
  font-size: 11px;
  color: #64748b;
  line-height: 1.35;
}
.cam-slot {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: #fff;
  border: 1px solid rgba(15, 23, 42, 0.1);
  border-radius: 12px;
  overflow-x: hidden;
  overflow-y: auto;
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.06);
}
.cam-slot__actions {
  flex-shrink: 0;
  margin-bottom: 2px;
}
.cam-slot__hd {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 10px;
  background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
  font-size: 12px;
  font-weight: 600;
  color: #334155;
}
.cam-slot__meta {
  font-size: 10px;
  font-weight: 500;
  color: #64748b;
  word-break: break-all;
}
.cam-slot__body {
  flex: 1 1 auto;
  min-height: 0;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.cam-placeholder {
  flex: 1;
  min-height: 100px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 16px 12px;
  background: repeating-linear-gradient(
    -45deg,
    #f1f5f9,
    #f1f5f9 8px,
    #e2e8f0 8px,
    #e2e8f0 16px
  );
  color: #64748b;
  text-align: center;
}
.cam-placeholder__title {
  font-size: 12px;
  font-weight: 600;
  color: #475569;
}
.cam-placeholder__sub {
  font-size: 11px;
  color: #94a3b8;
}
.cam-video-wrap--slot {
  padding-bottom: 0;
  height: 120px;
  min-height: 100px;
  border-radius: 8px;
}
.ez--compact {
  font-size: 11px;
  padding: 8px 10px;
  margin: 0;
}
.ptz--compact {
  margin-top: 0;
  flex-shrink: 0;
}
.ptz-speed {
  width: 72px;
  margin-left: 6px;
}
.cam-lightbox-title {
  font-weight: 600;
  color: #0f172a;
  font-size: 15px;
}
.cam-lightbox-body {
  padding: 0 2px 4px;
}
.cam-video-wrap--lightbox {
  padding-bottom: 0;
  aspect-ratio: 16 / 9;
  width: 100%;
  max-height: min(70vh, 620px);
  height: auto;
  border-radius: 10px;
}
.ptz-speed-dialog {
  width: 88px;
  margin-left: 8px;
}
.loc-page :deep(.cam-lightbox-dialog.el-dialog) {
  border-radius: 14px;
}
.loc-page :deep(.cam-lightbox-dialog .el-dialog__header) {
  padding-bottom: 8px;
  margin-right: 0;
}
.loc-page :deep(.cam-lightbox-dialog .el-dialog__body) {
  padding-top: 4px;
}
@media (max-width: 960px) {
  .rt-map-cam {
    flex-direction: column;
    min-height: 0;
  }
  .rt-map-cam__cams {
    flex: none;
    width: 100%;
    min-width: 0;
    flex-direction: row;
    flex-wrap: wrap;
  }
  .cam-slot {
    flex: 1 1 calc(33.333% - 8px);
    min-width: 160px;
    min-height: 200px;
  }
}
@media (max-width: 600px) {
  .rt-map-cam__cams {
    flex-direction: column;
  }
  .cam-slot {
    flex: none;
    min-height: 180px;
  }
}

.map-box {
  width: 100%;
  min-height: 420px;
  height: clamp(380px, 52vh, 520px);
  border-radius: 12px;
  margin: 0;
  border: 1px solid rgba(15, 23, 42, 0.1);
  box-shadow: 0 2px 16px rgba(15, 23, 42, 0.07);
  overflow: hidden;
  background: #e2e8f0;
}
.map-box--rt {
  flex: 1;
  width: 100%;
  min-height: clamp(400px, 52vh, 560px);
  height: auto;
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
