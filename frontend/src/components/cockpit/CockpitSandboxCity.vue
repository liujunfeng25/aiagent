<template>
  <div ref="rootRef" class="sandbox-city">
    <canvas ref="canvasRef" class="sandbox-city__canvas" />
    <p v-if="webglError" class="sandbox-city__err">{{ webglError }}</p>
  </div>
</template>

<script setup>
/**
 * 抽象北京「售楼处沙盘」：Three.js 体块城市 + 斜俯视 OrbitControls，非高德瓦片。
 */
import { ref, watch, onMounted, onUnmounted, shallowRef } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { lngLatToSandboxXZ, statusColor } from '../../utils/cockpitGeo.js'

const props = defineProps({
  vehicles: { type: Array, default: () => [] },
  warehouses: { type: Array, default: () => [] },
})

const HALF_EXTENT = 90
const BUILDING_GRID = 22

const rootRef = ref(null)
const canvasRef = ref(null)
const webglError = ref('')

/** @type {import('vue').ShallowRef<THREE.WebGLRenderer | null>} */
const rendererRef = shallowRef(null)
/** @type {import('vue').ShallowRef<THREE.Scene | null>} */
const sceneRef = shallowRef(null)
/** @type {import('vue').ShallowRef<THREE.PerspectiveCamera | null>} */
const cameraRef = shallowRef(null)
const controlsRef = shallowRef(null)

let rafId = 0
let resizeObserver = null
const markerGroup = new THREE.Group()
const buildingGroup = new THREE.Group()

function seeded01(i, j) {
  const n = Math.sin(i * 12.9898 + j * 78.233) * 43758.5453123
  return n - Math.floor(n)
}

function buildMaquette(scene) {
  const groundGeo = new THREE.PlaneGeometry(HALF_EXTENT * 2.2, HALF_EXTENT * 2.2, 1, 1)
  const groundMat = new THREE.MeshStandardMaterial({
    color: 0x0c1528,
    metalness: 0.15,
    roughness: 0.85,
    transparent: true,
    opacity: 0.92,
  })
  const ground = new THREE.Mesh(groundGeo, groundMat)
  ground.rotation.x = -Math.PI / 2
  ground.receiveShadow = true
  ground.position.y = 0
  scene.add(ground)

  const grid = new THREE.GridHelper(HALF_EXTENT * 2.1, 42, 0x22d3ee, 0x1e3a5f)
  grid.material.opacity = 0.25
  grid.material.transparent = true
  grid.position.y = 0.02
  scene.add(grid)

  const cell = (HALF_EXTENT * 2) / BUILDING_GRID
  const buildingMat = new THREE.MeshStandardMaterial({
    color: 0xe8eef8,
    metalness: 0.35,
    roughness: 0.45,
    emissive: new THREE.Color(0x223344),
    emissiveIntensity: 0.06,
  })

  for (let i = 0; i < BUILDING_GRID; i++) {
    for (let j = 0; j < BUILDING_GRID; j++) {
      const h = 4 + seeded01(i, j) * 38 + seeded01(j + 7, i + 3) * 12
      const w = cell * 0.72
      const mesh = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), buildingMat.clone())
      mesh.scale.set(w, h, w)
      const x = -HALF_EXTENT + cell * (i + 0.5)
      const z = -HALF_EXTENT + cell * (j + 0.5)
      mesh.position.set(x, h / 2, z)
      mesh.castShadow = true
      mesh.receiveShadow = true
      buildingGroup.add(mesh)
    }
  }
  buildingMat.dispose()
  scene.add(buildingGroup)
  scene.add(markerGroup)
}

function clearMarkers() {
  while (markerGroup.children.length) {
    const o = markerGroup.children[0]
    markerGroup.remove(o)
    if (o.geometry) o.geometry.dispose()
    if (o.material) {
      if (Array.isArray(o.material)) o.material.forEach((m) => m.dispose())
      else o.material.dispose()
    }
  }
}

function syncMarkers() {
  clearMarkers()

  ;(props.vehicles || []).forEach((v) => {
    const lng = Number(v.lng)
    const lat = Number(v.lat)
    if (!Number.isFinite(lng) || !Number.isFinite(lat)) return
    const { x, z } = lngLatToSandboxXZ(lng, lat, HALF_EXTENT)
    const col = statusColor(v.status)
    const mat = new THREE.MeshStandardMaterial({
      color: col,
      emissive: col,
      emissiveIntensity: 0.35,
      metalness: 0.4,
      roughness: 0.35,
    })
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(1.1, 16, 12), mat)
    mesh.position.set(x, 3.5, z)
    markerGroup.add(mesh)
  })

  ;(props.warehouses || []).forEach((w) => {
    const lng = Number(w.lng)
    const lat = Number(w.lat)
    if (!Number.isFinite(lng) || !Number.isFinite(lat)) return
    const { x, z } = lngLatToSandboxXZ(lng, lat, HALF_EXTENT)
    const mat = new THREE.MeshStandardMaterial({
      color: 0x38bdf8,
      emissive: 0x0ea5e9,
      emissiveIntensity: 0.25,
      metalness: 0.5,
      roughness: 0.3,
    })
    const mesh = new THREE.Mesh(new THREE.ConeGeometry(1.2, 2.2, 8), mat)
    mesh.position.set(x, 2.2, z)
    mesh.rotation.z = Math.PI
    markerGroup.add(mesh)
  })
}

function animate() {
  rafId = requestAnimationFrame(animate)
  const renderer = rendererRef.value
  const scene = sceneRef.value
  const camera = cameraRef.value
  const controls = controlsRef.value
  if (!renderer || !scene || !camera) return
  controls?.update()
  renderer.render(scene, camera)
}

function onResize() {
  const canvas = canvasRef.value
  const renderer = rendererRef.value
  const camera = cameraRef.value
  if (!canvas || !renderer || !camera || !rootRef.value) return
  const w = rootRef.value.clientWidth
  const h = rootRef.value.clientHeight
  if (w < 2 || h < 2) return
  camera.aspect = w / h
  camera.updateProjectionMatrix()
  renderer.setSize(w, h, false)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
}

function disposeScene(scene) {
  scene.traverse((obj) => {
    if (obj.geometry) obj.geometry.dispose()
    if (obj.material) {
      if (Array.isArray(obj.material)) obj.material.forEach((m) => m.dispose())
      else obj.material.dispose()
    }
  })
}

function init() {
  const canvas = canvasRef.value
  const root = rootRef.value
  if (!canvas || !root) return

  const scene = new THREE.Scene()
  scene.background = new THREE.Color(0x070b14)
  // 轻微景深雾：深蓝，避免灰白雾霾感
  scene.fog = new THREE.FogExp2(0x070b14, 0.0018)

  const camera = new THREE.PerspectiveCamera(48, 16 / 9, 0.5, 800)
  camera.position.set(95, 78, 95)
  camera.lookAt(0, 0, 0)

  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    alpha: false,
    powerPreference: 'high-performance',
  })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setSize(root.clientWidth, root.clientHeight, false)
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
  renderer.outputColorSpace = THREE.SRGBColorSpace
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.05

  const controls = new OrbitControls(camera, canvas)
  controls.target.set(0, 4, 0)
  controls.enableDamping = true
  controls.dampingFactor = 0.06
  controls.minDistance = 55
  controls.maxDistance = 220
  // 极角：约 35°–62° 俯视带（相对 Y 轴），接近斜 45° 鸟瞰
  controls.minPolarAngle = Math.PI * 0.22
  controls.maxPolarAngle = Math.PI * 0.48
  controls.maxAzimuthAngle = Infinity
  controls.update()

  const hemi = new THREE.HemisphereLight(0xa5d8ff, 0x0a1628, 0.85)
  scene.add(hemi)
  const dir = new THREE.DirectionalLight(0xffffff, 1.1)
  dir.position.set(60, 120, 40)
  dir.castShadow = true
  dir.shadow.mapSize.set(1024, 1024)
  dir.shadow.camera.near = 10
  dir.shadow.camera.far = 400
  dir.shadow.camera.left = -140
  dir.shadow.camera.right = 140
  dir.shadow.camera.top = 140
  dir.shadow.camera.bottom = -140
  scene.add(dir)
  const fill = new THREE.PointLight(0x22d3ee, 0.35, 400)
  fill.position.set(-40, 60, -30)
  scene.add(fill)

  buildMaquette(scene)
  syncMarkers()

  sceneRef.value = scene
  cameraRef.value = camera
  rendererRef.value = renderer
  controlsRef.value = controls

  resizeObserver = new ResizeObserver(() => onResize())
  resizeObserver.observe(root)
  onResize()
  animate()
}

onMounted(() => {
  try {
    init()
  } catch (e) {
    console.warn('[CockpitSandboxCity]', e)
    webglError.value = '三维沙盘初始化失败，请检查浏览器 WebGL'
  }
})

watch(
  () => [props.vehicles, props.warehouses],
  () => {
    if (sceneRef.value) syncMarkers()
  },
  { deep: true },
)

onUnmounted(() => {
  cancelAnimationFrame(rafId)
  if (resizeObserver && rootRef.value) {
    try {
      resizeObserver.unobserve(rootRef.value)
    } catch (_) { /* */ }
  }
  resizeObserver = null

  const renderer = rendererRef.value
  const scene = sceneRef.value
  const controls = controlsRef.value

  controlsRef.value = null
  rendererRef.value = null
  cameraRef.value = null
  sceneRef.value = null

  if (controls) controls.dispose()
  if (renderer) {
    renderer.dispose()
    renderer.forceContextLoss?.()
  }
  if (scene) {
    clearMarkers()
    disposeScene(scene)
  }
})
</script>

<style scoped>
.sandbox-city {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 260px;
  border-radius: 4px;
  overflow: hidden;
  background: radial-gradient(ellipse 120% 80% at 50% 20%, rgba(34, 211, 238, 0.06), transparent 55%),
    #070b14;
}

.sandbox-city__canvas {
  display: block;
  width: 100%;
  height: 100%;
}

.sandbox-city__err {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0;
  padding: 12px;
  font-size: 13px;
  color: rgba(248, 113, 113, 0.95);
  background: rgba(7, 11, 20, 0.85);
  z-index: 2;
}
</style>
