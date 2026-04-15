import request from './request'

/** 智能分单：只读抽样业务库订单/明细与供货方主数据。 */
export function fetchSmartSplitSeed() {
  return request.get('/governance/smart-split-seed')
}

export function confirmSmartSplit(payload) {
  return request.post('/governance/smart-split-confirm', payload)
}

export function fetchSmartSplitConfirmed(limit = 20) {
  return request.get('/governance/smart-split-confirmed', { params: { limit } })
}

export function fetchAmapJsConfig() {
  return request.get('/governance/amap-js-config')
}

export function geocodeSmartSplitAddresses(payload) {
  return request.post('/governance/smart-split-geocode', payload)
}

export function fetchDeliveryRouteToday() {
  return request.get('/governance/delivery-route-today')
}

/** 智能排线：今日送货司机聚合（含车牌、手机、订单数、去重客户数） */
export function fetchDeliveryRouteDrivers() {
  return request.get('/governance/delivery-route-drivers')
}

/** 智能排线：指定司机（或未指派）的今日订单；driver 为 driver_id 字符串或 __unassigned__ */
export function fetchDeliveryRouteOrders(driver) {
  return request.get('/governance/delivery-route-orders', {
    params: { driver: String(driver) },
  })
}

export function postSmartSplitSupplierRating(supplierId, rating) {
  return request.post('/governance/smart-split-supplier-rating', {
    supplier_id: supplierId,
    rating,
  })
}
