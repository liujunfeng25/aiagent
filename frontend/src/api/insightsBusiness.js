import request from './request'

export const insightsHealth = () => request.get('/insights/business/health')

export const ordersDaily = (params) => request.get('/insights/business/orders-daily', { params })

export const ordersTopMembers = (params) => request.get('/insights/business/orders-top-members', { params })

export const backorderDaily = (params) => request.get('/insights/business/backorder-daily', { params })

export const xinfadiSummarySeries = (params) =>
  request.get('/insights/business/xinfadi-summary-series', { params })
