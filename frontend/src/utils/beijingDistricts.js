/**
 * 北京市行政区划：名称列表 + 视野限制矩形（GCJ-02，与高德一致）。
 * 若边界与高德行政区略有偏差，可微调 SW/NE。
 */
export const BEIJING_BOUNDS_SW = [115.42, 39.44]
export const BEIJING_BOUNDS_NE = [117.52, 41.06]

/** 北京市 16 个市辖区名称（展示用） */
export const BEIJING_DISTRICT_NAMES = [
  '东城区',
  '西城区',
  '朝阳区',
  '丰台区',
  '石景山区',
  '海淀区',
  '门头沟区',
  '房山区',
  '通州区',
  '顺义区',
  '昌平区',
  '大兴区',
  '怀柔区',
  '平谷区',
  '密云区',
  '延庆区',
]

/**
 * 与名称一一对应的高德 adcode（用于 DistrictSearch，比纯中文名更稳定）
 */
export const BEIJING_DISTRICT_ADCODE = [
  '110101',
  '110102',
  '110105',
  '110106',
  '110107',
  '110108',
  '110109',
  '110111',
  '110112',
  '110113',
  '110114',
  '110115',
  '110116',
  '110117',
  '110118',
  '110119',
]

/** 北京市级 adcode */
export const BEIJING_CITY_ADCODE = '110000'

/**
 * 数据驾驶舱地图缩放范围：提高 minZoom 可避免缩放过小露出河北省等市外区域。
 * 须与 map.setLimitBounds 配合使用。
 */
export const COCKPIT_MAP_ZOOM_MIN = 10
export const COCKPIT_MAP_ZOOM_MAX = 18
