import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'Dashboard', component: () => import('../views/Dashboard.vue'), meta: { title: '工作台' } },
  { path: '/datasources', name: 'DataSources', component: () => import('../views/DataSources.vue'), meta: { title: '数据源' } },
  { path: '/datasets', name: 'Datasets', component: () => import('../views/Datasets.vue'), meta: { title: '数据集' } },
  { path: '/categories', name: 'Categories', component: () => import('../views/Categories.vue'), meta: { title: '类别管理' } },
  { path: '/categories/:name', name: 'CategoryDetail', component: () => import('../views/CategoryDetail.vue'), meta: { title: '类别详情' } },
  { path: '/training', name: 'Training', component: () => import('../views/Training.vue'), meta: { title: '训练管理' } },
  { path: '/models', name: 'Models', component: () => import('../views/Models.vue'), meta: { title: '模型库' } },
  { path: '/recognition', name: 'Recognition', component: () => import('../views/Recognition.vue'), meta: { title: '识别中心' } },
  { path: '/documents', name: 'Documents', component: () => import('../views/Documents.vue'), meta: { title: '票据识别' } },
  { path: '/insights', name: 'DataInsights', component: () => import('../views/DataInsights.vue'), meta: { title: '数据洞察' } },
  { path: '/analysis', redirect: (to) => ({ path: '/insights', query: { ...to.query, tab: 'orders' } }) },
  { path: '/price', name: 'Price', component: () => import('../views/Price.vue'), meta: { title: '报价抓取' } },
  { path: '/system', name: 'System', component: () => import('../views/System.vue'), meta: { title: '系统管理' } },
  { path: '/logistics', name: 'LogisticsIndex', component: () => import('../views/LogisticsIndex.vue'), meta: { title: '智能物流' } },
  { path: '/logistics/vehicle/:id/bind', name: 'LogisticsBind', component: () => import('../views/LogisticsBind.vue'), meta: { title: '设备绑定' } },
  { path: '/logistics/vehicle/:id/location', name: 'LogisticsVehicleLocation', component: () => import('../views/LogisticsVehicleLocation.vue'), meta: { title: '车辆位置' } },
  { path: '/logistics/fees', name: 'LogisticsFee', component: () => import('../views/LogisticsFee.vue'), meta: { title: '物流费用' } },
  {
    path: '/logistics/location',
    redirect: (to) => {
      const vid = to.query.vehicleId
      if (vid) {
        return { path: `/logistics/vehicle/${vid}/location`, query: { plateno: to.query.plateno || '' } }
      }
      return { path: '/logistics' }
    },
  },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
