/**
 * 驾驶舱大屏 mock 数据。
 * 后端 /api/insights/business/* 不可达时回退使用。
 */

function last30Days() {
  const days = []
  const now = new Date()
  for (let i = 29; i >= 0; i--) {
    const d = new Date(now)
    d.setDate(d.getDate() - i)
    const m = d.getMonth() + 1
    const dd = d.getDate()
    days.push(`${m}/${dd}`)
  }
  return days
}

function rndInt(min, max) {
  return Math.floor(min + Math.random() * (max - min + 1))
}

export function mockOrdersDailySeries() {
  const days = last30Days()
  return days.map((day) => ({
    day,
    order_count: rndInt(40, 180),
    gmv: +(rndInt(8000, 45000) + Math.random()).toFixed(2),
  }))
}

export function mockOrdersTopMembers() {
  const names = [
    '永辉超市-朝阳店', '盒马鲜生-望京', '物美超市-海淀',
    '大润发-丰台', '华联超市-通州', '京客隆-昌平',
    '七鲜超市-东城', '首航超市-西城', '超市发-石景山',
    '天虹超市-顺义',
  ]
  return names.map((name, i) => ({
    member_id: 1000 + i,
    member_name: name,
    order_count: rndInt(20, 200 - i * 12),
    gmv: +(rndInt(5000, 60000 - i * 3500) + Math.random()).toFixed(2),
  }))
}

export function mockGoodsTop() {
  const goods = [
    '精品五花肉', '去骨牛腿肉', '三文鱼段', '大黄鱼',
    '有机西兰花', '荷兰豆', '智利车厘子', '泰国榴莲',
    '鲜虾仁', '澳洲牛排',
  ]
  return goods.map((name, i) => ({
    goods_name: name,
    total_qty: rndInt(80, 500 - i * 30),
    total_amount: +(rndInt(3000, 28000 - i * 1800) + Math.random()).toFixed(2),
  }))
}

export function mockRegionDistribution() {
  const regions = [
    { region_name: '朝阳区', order_count: rndInt(120, 250) },
    { region_name: '海淀区', order_count: rndInt(100, 220) },
    { region_name: '丰台区', order_count: rndInt(70, 160) },
    { region_name: '东城区', order_count: rndInt(50, 130) },
    { region_name: '西城区', order_count: rndInt(40, 110) },
    { region_name: '通州区', order_count: rndInt(35, 100) },
    { region_name: '昌平区', order_count: rndInt(30, 90) },
    { region_name: '大兴区', order_count: rndInt(25, 80) },
    { region_name: '顺义区', order_count: rndInt(20, 70) },
    { region_name: '石景山区', order_count: rndInt(15, 55) },
  ]
  regions.forEach((r) => { r.gmv = +(r.order_count * rndInt(120, 350) + Math.random()).toFixed(2) })
  return regions
}

export function mockKpi() {
  return {
    todayOrders: rndInt(120, 350),
    todayGmv: +(rndInt(25000, 85000) + Math.random()).toFixed(2),
    avgOrderAmount: +(rndInt(150, 380) + Math.random()).toFixed(2),
    deliveryRate: +(92 + Math.random() * 7).toFixed(1),
    returnRate: +(0.5 + Math.random() * 3).toFixed(1),
    newCustomers: rndInt(3, 18),
  }
}
