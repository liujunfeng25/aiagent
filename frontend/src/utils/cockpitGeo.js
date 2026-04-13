/** 北京市域 GCJ-02 大致范围（与 AMapMonitor 一致，用于沙盘经纬度映射） */
export const BJ_BOUNDS_SW = [115.42, 39.44]
export const BJ_BOUNDS_NE = [117.52, 41.06]
export const BJ_CENTER_LNG = 116.407526
export const BJ_CENTER_LAT = 39.90403

/**
 * 将 GCJ 经纬度映射到沙盘平面 XZ（中心原点，约 [-halfExtent, halfExtent]）
 * @param {number} lng
 * @param {number} lat
 * @param {number} halfExtent 沙盘半边长（世界单位）
 */
export function lngLatToSandboxXZ(lng, lat, halfExtent = 90) {
  const [swLng, swLat] = BJ_BOUNDS_SW
  const [neLng, neLat] = BJ_BOUNDS_NE
  const u = (Number(lng) - swLng) / (neLng - swLng)
  const v = (Number(lat) - swLat) / (neLat - swLat)
  const x = (u - 0.5) * 2 * halfExtent
  const z = (v - 0.5) * 2 * halfExtent
  return { x, z }
}

export function statusColor(status) {
  if (status === 'running') return 0x34d399
  if (status === 'alarm') return 0xf87171
  return 0x60a5fa
}

export function statusLabel(status) {
  if (status === 'running') return '运行中'
  if (status === 'alarm') return '告警'
  return '停车'
}
