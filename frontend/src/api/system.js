import request from './request'

export const getLogs = (limit = 100) => request.get('/system/logs', { params: { limit } })
