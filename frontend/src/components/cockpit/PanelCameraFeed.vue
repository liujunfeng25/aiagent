<template>
  <div class="cf-root">
    <CockpitPanelBlue title="视频监控" title-en="VIDEO FEED">
      <div class="cf">
        <div v-for="cam in data" :key="cam.id" class="cf__cell">
          <div
            class="cf__thumb"
            :class="{ 'cf__thumb--click': canOpenLightbox(cam) }"
            role="button"
            :tabindex="canOpenLightbox(cam) ? 0 : -1"
            @click="onThumbClick(cam)"
            @keydown.enter.prevent="onThumbClick(cam)"
            @keydown.space.prevent="onThumbClick(cam)"
          >
            <template v-if="canYs7Inline(cam)">
              <div :id="ezContainerId(cam)" class="cf__ez" />
            </template>
            <video
              v-else-if="effectiveHttpPlayUrl(cam)"
              class="cf__video"
              :src="effectiveHttpPlayUrl(cam)"
              muted
              playsinline
              autoplay
              controls
              @click.stop
            />
            <img v-else-if="cam.thumbUrl" :src="cam.thumbUrl" :alt="cam.name" class="cf__img" @click.stop />
            <div v-else class="cf__placeholder">
              <span class="cf__ph-shape" aria-hidden="true" />
              <span class="cf__cam-no-signal">{{ cam.status === 'offline' ? '离线' : 'LIVE' }}</span>
            </div>
          </div>
          <div class="cf__info">
            <span class="cf__name" :title="cam.name">{{ cam.name }}</span>
            <span :class="['cf__dot', cam.status === 'online' ? 'cf__dot--on' : 'cf__dot--off']" />
          </div>
        </div>
      </div>
    </CockpitPanelBlue>

    <el-dialog
      v-model="camDialogOpen"
      class="cf-lightbox-dialog"
      width="min(960px, 94vw)"
      align-center
      destroy-on-close
      :close-on-click-modal="true"
      @closed="onCamDialogClosed"
    >
      <template #header>
        <span class="cf-lightbox-title">实时画面 · {{ camDialogCam?.device_name || camDialogCam?.name || '摄像头' }}</span>
      </template>
      <div v-if="camDialogCam" class="cf-lightbox-body">
        <p v-if="camDialogCam.error" class="cf-lightbox-err">{{ camDialogCam.error }}</p>
        <template v-else>
          <template v-if="camDialogCam.camera_source === 'ys7' && isEzopenUrl(camDialogCam.hls)">
            <p v-if="!camDialogCam.ys7_access_token" class="cf-lightbox-err">萤石播放缺少 accessToken</p>
            <div v-else class="cf-video-wrap cf-video-wrap--lightbox">
              <div :id="ezContainerIdDialog(camDialogCam)" class="cf-ez" />
            </div>
          </template>
          <div v-else-if="effectiveHttpPlayUrl(camDialogCam)" class="cf-video-wrap cf-video-wrap--lightbox">
            <video class="cf-v" controls playsinline :src="effectiveHttpPlayUrl(camDialogCam)" />
          </div>
          <div v-else-if="camDialogCam.hls" class="cf-ez-txt">{{ camDialogCam.hls }}</div>
          <div
            v-if="showPtzFor(camDialogCam)"
            class="cf-ptz"
          >
            <span class="cf-ptz-lbl">云台</span>
            <el-button-group>
              <el-button size="small" @mousedown="ptzStart(camDialogCam, 0)" @mouseup="ptzStop(camDialogCam)" @touchstart.prevent="ptzStart(camDialogCam, 0)" @touchend.prevent="ptzStop(camDialogCam)">上</el-button>
              <el-button size="small" @mousedown="ptzStart(camDialogCam, 1)" @mouseup="ptzStop(camDialogCam)">下</el-button>
              <el-button size="small" @mousedown="ptzStart(camDialogCam, 2)" @mouseup="ptzStop(camDialogCam)">左</el-button>
              <el-button size="small" @mousedown="ptzStart(camDialogCam, 3)" @mouseup="ptzStop(camDialogCam)">右</el-button>
            </el-button-group>
            <el-select v-model="ptzSpeed" size="small" class="cf-ptz-speed">
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
import { ref, watch, nextTick, onUnmounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import CockpitPanelBlue from './CockpitPanelBlue.vue'
import { sxwLogisticsAxiosParams } from '../../utils/sxwLogisticsTenant.js'

const props = defineProps({
  data: { type: Array, default: () => [] },
})

function isHttpStreamUrl(u) {
  if (!u || typeof u !== 'string') return false
  const s = u.trim().toLowerCase()
  return s.startsWith('http://') || s.startsWith('https://')
}

function isEzopenUrl(u) {
  if (!u || typeof u !== 'string') return false
  return u.trim().toLowerCase().startsWith('ezopen://')
}

function ezPlayerKey(cam) {
  if (cam?.camera_device_id != null && cam.camera_device_id !== '') return String(cam.camera_device_id)
  return cam?.id != null ? String(cam.id) : ''
}

function ezContainerId(cam) {
  return `cockpit-cf-ez-${ezPlayerKey(cam)}`
}

function ezContainerIdDialog(cam) {
  return `cockpit-cf-ez-dialog-${ezPlayerKey(cam)}`
}

function canYs7Inline(cam) {
  return Boolean(
    cam
    && !cam.error
    && cam.camera_source === 'ys7'
    && isEzopenUrl(cam.hls)
    && cam.ys7_access_token,
  )
}

function effectiveHttpPlayUrl(cam) {
  if (cam?.streamUrl && isHttpStreamUrl(cam.streamUrl)) return cam.streamUrl.trim()
  if (cam?.hls && isHttpStreamUrl(cam.hls)) return cam.hls.trim()
  return ''
}

function canOpenLightbox(cam) {
  if (!cam || cam.error) return false
  if (canYs7Inline(cam)) return true
  return Boolean(effectiveHttpPlayUrl(cam))
}

function showPtzFor(cam) {
  return Boolean(
    cam
    && !cam.error
    && cam.camera_source === 'ys7'
    && cam.camera_device_id != null
    && cam.camera_device_id !== ''
    && cam.vehicle_id != null
    && cam.vehicle_id !== '',
  )
}

function onThumbClick(cam) {
  if (!canOpenLightbox(cam)) return
  if (cam.camera_source === 'ys7' && isEzopenUrl(cam.hls) && !cam.ys7_access_token) {
    ElMessage.warning('缺少播放凭证')
    return
  }
  if (cam.camera_source === 'ys7' && isEzopenUrl(cam.hls) && cam.ys7_access_token) {
    destroyYs7EzPlayer(ezPlayerKey(cam))
  }
  camDialogCam.value = cam
  camDialogOpen.value = true
}

const camDialogOpen = ref(false)
const camDialogCam = ref(null)
const ptzSpeed = ref(1)
let _ptzCam = null

async function ptzStart(cam, direction) {
  _ptzCam = cam
  const vid = cam?.vehicle_id
  if (vid == null || vid === '') return
  try {
    const { data } = await axios.post(
      '/api/logistics/sxw/cameras/ptz',
      {
        vehicle_id: vid,
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
  if (!c?.vehicle_id || c.camera_device_id == null) return
  try {
    await axios.post(
      '/api/logistics/sxw/cameras/ptz',
      {
        vehicle_id: c.vehicle_id,
        camera_device_id: c.camera_device_id,
        op: 'stop',
        direction: 0,
        speed: 1,
      },
      { params: sxwLogisticsAxiosParams() },
    )
  } catch (_) { /* ignore */ }
}

const ys7EzPlayers = new Map()
let ezUIKitScriptPromise = null

function ensureEzUIKitScript() {
  if (typeof window === 'undefined') return Promise.reject(new Error('no window'))
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

function destroyYs7EzPlayer(key) {
  const p = ys7EzPlayers.get(key)
  if (!p) return
  try {
    if (typeof p.destroy === 'function') p.destroy()
  } catch (_) { /* ignore */ }
  try {
    if (typeof p.stop === 'function') p.stop()
  } catch (_) { /* ignore */ }
  ys7EzPlayers.delete(key)
}

function destroyAllYs7EzPlayers() {
  for (const k of [...ys7EzPlayers.keys()]) destroyYs7EzPlayer(k)
}

async function syncYs7DialogPlayer() {
  const cam = camDialogCam.value
  if (!camDialogOpen.value || !cam || cam.error) return
  if (cam.camera_source !== 'ys7' || !isEzopenUrl(cam.hls) || !cam.ys7_access_token) return
  await nextTick()
  const elId = ezContainerIdDialog(cam)
  const el = document.getElementById(elId)
  if (!el) return
  destroyYs7EzPlayer(`dialog:${ezPlayerKey(cam)}`)
  try {
    await ensureEzUIKitScript()
    const wrap = el.closest('.cf-video-wrap--lightbox')
    const w = Math.max(640, wrap?.clientWidth || el.clientWidth || 880)
    const h = Math.max(360, Math.floor((w * 9) / 16))
    const player = new window.EZUIKit.EZUIKitPlayer({
      id: elId,
      accessToken: cam.ys7_access_token,
      url: cam.hls.trim(),
      width: w,
      height: h,
    })
    ys7EzPlayers.set(`dialog:${ezPlayerKey(cam)}`, player)
  } catch (_) {
    ElMessage.error('萤石播放器加载失败')
  }
}

function onCamDialogClosed() {
  const cam = camDialogCam.value
  if (cam) destroyYs7EzPlayer(`dialog:${ezPlayerKey(cam)}`)
  camDialogCam.value = null
  nextTick(() => { void syncYs7EzUIKitPlayers() })
}

watch(camDialogOpen, async (open) => {
  if (!open) return
  await nextTick()
  await syncYs7DialogPlayer()
})

async function syncYs7EzUIKitPlayers() {
  await nextTick()
  const cams = props.data || []
  const keep = new Set()
  for (const cam of cams) {
    if (!canYs7Inline(cam)) continue
    if (
      camDialogOpen.value
      && camDialogCam.value
      && ezPlayerKey(cam) === ezPlayerKey(camDialogCam.value)
    ) {
      continue
    }
    const key = ezPlayerKey(cam)
    if (!key) continue
    keep.add(key)
    const elId = ezContainerId(cam)
    const el = document.getElementById(elId)
    if (!el) continue
    destroyYs7EzPlayer(key)
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
      ys7EzPlayers.set(key, player)
    } catch (_) { /* ignore */ }
  }
  for (const id of [...ys7EzPlayers.keys()]) {
    if (id.startsWith('dialog:')) continue
    if (!keep.has(id)) destroyYs7EzPlayer(id)
  }
}

watch(() => props.data, () => { void syncYs7EzUIKitPlayers() }, { deep: true, flush: 'post', immediate: true })

onUnmounted(() => destroyAllYs7EzPlayers())
</script>

<style scoped>
.cf-root {
  height: 100%;
  min-height: 0;
}

.cf {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  height: 100%;
}

.cf__cell {
  display: flex;
  flex-direction: column;
  border-radius: 4px;
  overflow: hidden;
  background: rgba(5, 12, 35, 0.6);
  border: 1px solid rgba(30, 144, 255, 0.12);
}

.cf__thumb {
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.cf__thumb--click {
  cursor: pointer;
}

.cf__img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.cf__video {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #0a0f1a;
  vertical-align: middle;
}

.cf__ez {
  width: 100%;
  height: 100%;
  min-height: 72px;
  background: #0a0f1a;
}

.cf__placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  width: 100%;
  height: 100%;
  background: linear-gradient(180deg, rgba(8, 20, 60, 0.9), rgba(5, 12, 35, 0.95));
}

.cf__ph-shape {
  width: 32px;
  height: 22px;
  border: 2px solid rgba(140, 170, 220, 0.28);
  border-radius: 4px;
  box-shadow: inset 0 0 8px rgba(30, 144, 255, 0.08);
}

.cf__cam-no-signal {
  font-size: 10px;
  letter-spacing: 0.15em;
  color: rgba(140, 170, 220, 0.5);
  font-weight: 600;
}

.cf__info {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px;
  background: rgba(5, 12, 35, 0.8);
  border-top: 1px solid rgba(30, 144, 255, 0.1);
}

.cf__name {
  flex: 1;
  font-size: 10px;
  color: #cbd5e1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cf__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.cf__dot--on {
  background: #34d399;
  box-shadow: 0 0 6px rgba(52, 211, 153, 0.7);
}

.cf__dot--off {
  background: #64748b;
}

.cf-lightbox-title {
  font-weight: 600;
  color: #e2e8f0;
  font-size: 15px;
}

.cf-lightbox-body {
  padding: 0 2px 4px;
}

.cf-lightbox-err {
  color: #f87171;
  font-size: 13px;
  margin: 0 0 8px;
}

.cf-video-wrap {
  position: relative;
  width: 100%;
  overflow: hidden;
  background: #0a0a0a;
  border: 1px solid rgba(30, 144, 255, 0.2);
  border-radius: 10px;
}

.cf-video-wrap--lightbox {
  aspect-ratio: 16 / 9;
  max-height: min(70vh, 620px);
  height: auto;
}

.cf-video-wrap .cf-v,
.cf-video-wrap .cf-ez {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  min-height: 0;
}

.cf-v {
  object-fit: contain;
  background: #000;
}

.cf-ez {
  background: #000;
}

.cf-ez-txt {
  font-size: 12px;
  color: #94a3b8;
  word-break: break-all;
}

.cf-ptz {
  margin-top: 14px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.cf-ptz-lbl {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #94a3b8;
  margin-right: 4px;
}

.cf-ptz-speed {
  width: 88px;
  margin-left: 8px;
}

.cf-root :deep(.cf-lightbox-dialog.el-dialog) {
  border-radius: 14px;
  background: linear-gradient(180deg, #0f172a 0%, #0b1224 100%);
  border: 1px solid rgba(30, 144, 255, 0.2);
}

.cf-root :deep(.cf-lightbox-dialog .el-dialog__header) {
  padding-bottom: 8px;
  margin-right: 0;
}

.cf-root :deep(.cf-lightbox-dialog .el-dialog__title) {
  color: #e2e8f0;
}

.cf-root :deep(.cf-lightbox-dialog .el-dialog__headerbtn .el-dialog__close) {
  color: #94a3b8;
}

.cf-root :deep(.cf-lightbox-dialog .el-dialog__body) {
  padding-top: 4px;
  color: #cbd5e1;
}
</style>
