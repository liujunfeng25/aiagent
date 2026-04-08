/**
 * 物联监控大屏 mock 数据。
 * 后端 IoT API 不可达时回退使用。
 */

function rndInt(min, max) {
  return Math.floor(min + Math.random() * (max - min + 1))
}

function pad2(n) { return n < 10 ? `0${n}` : `${n}` }

function recentTime(minutesAgo) {
  const d = new Date(Date.now() - minutesAgo * 60000)
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`
}

export function mockDeviceStatus() {
  const total = rndInt(40, 60)
  const online = rndInt(Math.floor(total * 0.7), total - 2)
  const alarm = rndInt(1, 5)
  const offline = total - online
  return {
    total,
    online,
    offline,
    alarm,
    onlineRate: +((online / total) * 100).toFixed(1),
  }
}

export function mockAllCameras() {
  return [
    { id: 'cam-01', name: '朝阳仓-入口', status: 'online', bindTarget: '朝阳冷链仓', thumbUrl: '' },
    { id: 'cam-02', name: '京A·88521-车载', status: 'online', bindTarget: '京A·88521', thumbUrl: '' },
    { id: 'cam-03', name: '海淀仓-月台', status: 'offline', bindTarget: '海淀冷链仓', thumbUrl: '' },
    { id: 'cam-04', name: '京B·33692-车载', status: 'online', bindTarget: '京B·33692', thumbUrl: '' },
    { id: 'cam-05', name: '丰台仓-入口', status: 'online', bindTarget: '丰台冷链仓', thumbUrl: '' },
    { id: 'cam-06', name: '京C·77103-车载', status: 'offline', bindTarget: '京C·77103', thumbUrl: '' },
    { id: 'cam-07', name: '朝阳仓-月台', status: 'online', bindTarget: '朝阳冷链仓', thumbUrl: '' },
    { id: 'cam-08', name: '海淀仓-入口', status: 'online', bindTarget: '海淀冷链仓', thumbUrl: '' },
    { id: 'cam-09', name: '京D·12045-车载', status: 'online', bindTarget: '京D·12045', thumbUrl: '' },
    { id: 'cam-10', name: '丰台仓-月台', status: 'offline', bindTarget: '丰台冷链仓', thumbUrl: '' },
  ]
}

export function mockCameraList() {
  const all = mockAllCameras()
  return all.slice(0, 4)
}

export function mockDeviceBindings() {
  const plates = [
    '京A·88521', '京B·33692', '京C·77103', '京D·12045',
    '京E·56738', '京F·90821', '京G·44210', '京H·65839',
  ]
  return plates.map((p) => ({
    plateno: p,
    camera: rndInt(0, 1) ? `${p}-车载` : '--',
    beidou: `BD-${rndInt(10000, 99999)}`,
    tempSensor: rndInt(0, 1) ? `TH-${rndInt(1000, 9999)}` : '--',
  }))
}

export const TEMP_THRESHOLD = 8

export function mockTempHumidity24h() {
  const now = new Date()
  return Array.from({ length: 24 }, (_, i) => {
    const h = (now.getHours() - 23 + i + 24) % 24
    return {
      hour: `${pad2(h)}:00`,
      temperature: +(rndInt(20, 60) / 10 + 2).toFixed(1),
      humidity: +(rndInt(550, 850) / 10).toFixed(1),
    }
  })
}

export function mockWarehouses() {
  return [
    { id: 'wh-1', name: '朝阳冷链仓', address: '北京市朝阳区金盏乡', lng: 116.532, lat: 39.948, cameraCount: 4 },
    { id: 'wh-2', name: '海淀冷链仓', address: '北京市海淀区西北旺', lng: 116.228, lat: 40.052, cameraCount: 3 },
    { id: 'wh-3', name: '丰台冷链仓', address: '北京市丰台区花乡', lng: 116.312, lat: 39.828, cameraCount: 2 },
  ]
}
