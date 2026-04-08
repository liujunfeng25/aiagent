import request from './request'

export const list = () => request.get('/models/')
export const get = (id) => request.get(`/models/${id}`)
export const rename = (id, name) => request.patch(`/models/${id}`, { name })
export const deploy = (id) => request.post(`/models/${id}/deploy`)
export const syncDisplayNames = () => request.post('/models/sync-display-names')
