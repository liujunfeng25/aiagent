import request from './request'

export const list = () => request.get('/datasources/')
export const create = (data) => request.post('/datasources/', data)
export const update = (id, data) => request.put(`/datasources/${id}`, data)
export const remove = (id) => request.delete(`/datasources/${id}`)
export const test = (id) => request.post(`/datasources/${id}/test`)
export const getTables = (id) => request.get(`/datasources/${id}/tables`)
