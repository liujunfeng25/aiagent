<template>
  <div class="logistics-location">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>实时位置 / 历史轨迹 — {{ plateno }}</span>
          <el-button @click="$router.back()">返回</el-button>
        </div>
      </template>

      <el-tabs v-model="activeTab" @tab-change="onTabChange">
        <el-tab-pane label="地图轨迹" name="map">
          <el-form :inline="true" :model="queryForm">
            <el-form-item label="开始时间">
              <el-date-picker
                v-model="queryForm.start_time"
                type="datetime"
                format="YYYY-MM-DD HH:mm:ss"
                value-format="YYYY-MM-DD HH:mm:ss"
                placeholder="开始时间"
              />
            </el-form-item>
            <el-form-item label="结束时间">
              <el-date-picker
                v-model="queryForm.end_time"
                type="datetime"
                format="YYYY-MM-DD HH:mm:ss"
                value-format="YYYY-MM-DD HH:mm:ss"
                placeholder="结束时间"
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadTrack">查历史轨迹</el-button>
              <el-button @click="loadRealtime">实时位置</el-button>
            </el-form-item>
          </el-form>

          <div style="margin-bottom: 10px; color: #666; font-size: 13px;">
            轨迹点数：{{ trackPoints.length }} &nbsp;|&nbsp;
            <span v-if="realtimeInfo">
              速度：{{ realtimeInfo.speed }} km/h &nbsp; 定位时间：{{ realtimeInfo.gps_time }}
            </span>
          </div>

          <div ref="mapRef" style="width: 100%; height: 520px; border-radius: 6px;"></div>
        </el-tab-pane>
        <el-tab-pane label="车载摄像头" name="cam">
          <div style="margin-bottom: 12px;">
            <el-button type="primary" size="small" @click="loadCamerasLive">刷新直播地址</el-button>
            <span style="margin-left: 12px; color: #909399; font-size: 13px;">
              与食迅后台「实时监控」一致，展示本车在 sl_vehicle_bind_camera 下已绑定的设备直播流（萤石/乐橙）。
            </span>
          </div>
          <template v-if="!cameraStreams.length">
            <el-empty description="未绑定摄像头或无有效直播地址" />
          </template>
          <div v-else class="cam-grid">
            <div v-for="(c, i) in cameraStreams" :key="i" class="cam-card">
              <div class="cam-title">{{ c.name || '摄像头' }} · {{ c.brand }}</div>
              <p v-if="c.error" class="cam-err">{{ c.error }}</p>
              <template v-else>
                <video
                  v-if="c.url"
                  class="cam-video"
                  controls
                  playsinline
                  :src="c.url"
                />
                <div v-else class="cam-err">暂无播放地址</div>
                <a v-if="c.url" :href="c.url" target="_blank" rel="noopener" class="cam-link">新窗口打开</a>
              </template>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { sxwLogisticsAxiosParams } from '../utils/sxwLogisticsTenant'

const route = useRoute()
const vehicleId = route.query.vehicleId
const plateno = route.query.plateno || '未知车辆'

const mapRef = ref(null)
const activeTab = ref('map')
const trackPoints = ref([])
const realtimeInfo = ref(null)
const cameraStreams = ref([])
let _map = null
let _polyline = null
let _markers = []

const queryForm = reactive({
  start_time: '',
  end_time: '',
})

onMounted(async () => {
  await initMap()
  loadRealtime()
})

function onTabChange(name) {
  if (name === 'cam') loadCamerasLive()
}

async function loadCamerasLive() {
  if (!vehicleId) return
  try {
    const { data } = await axios.get(`/api/logistics/vehicles/${vehicleId}/cameras/live`, {
      params: sxwLogisticsAxiosParams(),
    })
    cameraStreams.value = data.data || []
    if (!cameraStreams.value.length) {
      ElMessage.info('当前车辆未绑定摄像头或上游未返回地址')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '获取直播地址失败')
  }
}

onUnmounted(() => {
  if (_map) { _map.destroy() }
})

async function initMap() {
  const { data } = await axios.get('/api/logistics/amap-config')
  const { key, securityJsCode } = data.data
  if (!key) {
    ElMessage.warning('未配置高德地图 API Key，地图无法显示')
    return
  }
  // 动态加载高德地图 JS API
  window._AMapSecurityConfig = { securityJsCode }
  await loadScript(`https://webapi.amap.com/maps?v=2.0&key=${key}`)
  _map = new window.AMap.Map(mapRef.value, {
    zoom: 12,
    center: [116.397428, 39.90923],
    mapStyle: 'amap://styles/normal',
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
  if (!vehicleId) return
  try {
    const { data } = await axios.get(`/api/logistics/vehicles/${vehicleId}/location`, { params: sxwLogisticsAxiosParams() })
    const pt = data.data
    if (!pt || !pt.lat) { ElMessage.warning('未获取到位置信息'); return }
    realtimeInfo.value = pt
    clearMap()
    if (!_map) return
    const marker = new window.AMap.Marker({
      position: [pt.lng, pt.lat],
      title: plateno,
    })
    _map.add(marker)
    _markers.push(marker)
    _map.setCenter([pt.lng, pt.lat])
    _map.setZoom(15)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '获取实时位置失败')
  }
}

async function loadTrack() {
  if (!vehicleId || !queryForm.start_time || !queryForm.end_time) {
    ElMessage.warning('请选择时间范围')
    return
  }
  try {
    const { data } = await axios.get(`/api/logistics/vehicles/${vehicleId}/track`, {
      params: sxwLogisticsAxiosParams({ start_time: queryForm.start_time, end_time: queryForm.end_time }),
    })
    const points = data.data || []
    trackPoints.value = points
    if (!points.length) { ElMessage.info('该时段无轨迹数据'); return }
    clearMap()
    if (!_map) return
    const path = points.map(p => [p.lng, p.lat])
    _polyline = new window.AMap.Polyline({
      path,
      strokeColor: '#1890ff',
      strokeWeight: 4,
      strokeOpacity: 0.9,
    })
    _map.add(_polyline)
    // 起点/终点标记
    addEndMarker(points[0], '起')
    addEndMarker(points[points.length - 1], '终')
    _map.setFitView()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '获取历史轨迹失败')
  }
}

function addEndMarker(pt, label) {
  const marker = new window.AMap.Marker({
    position: [pt.lng, pt.lat],
    label: { content: label, offset: new window.AMap.Pixel(0, -30) },
  })
  _map.add(marker)
  _markers.push(marker)
}

function clearMap() {
  if (_polyline) { _map.remove(_polyline); _polyline = null }
  _markers.forEach(m => _map.remove(m))
  _markers = []
}
</script>

<style scoped>
.logistics-location { padding: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.cam-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}
.cam-card {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 12px;
  background: #fafafa;
}
.cam-title { font-weight: 600; margin-bottom: 8px; }
.cam-video {
  width: 100%;
  max-height: 240px;
  background: #000;
  border-radius: 4px;
}
.cam-err { color: #f56c6c; font-size: 13px; margin: 8px 0; }
.cam-link { font-size: 13px; margin-top: 8px; display: inline-block; }
</style>
