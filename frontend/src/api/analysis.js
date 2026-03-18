import request from './request'

export const runQuery = (data) => request.post('/analysis/query', data)
