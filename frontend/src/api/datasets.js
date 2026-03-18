import request from './request'

export const list = () => request.get('/datasets/')
export const create = (data) => request.post('/datasets/', data)
export const get = (id) => request.get(`/datasets/${id}`)
export const update = (id, data) => request.patch(`/datasets/${id}`, data)
export const preview = (id, limit = 20) => request.get(`/datasets/${id}/preview`, { params: { limit } })
export const remove = (id) => request.delete(`/datasets/${id}`)

// 该数据集下的类别（归属关系）
export const listCategories = (datasetId) => request.get(`/datasets/${datasetId}/categories`)
export const createCategory = (datasetId, data) => request.post(`/datasets/${datasetId}/categories`, data)
export const deleteCategory = (datasetId, name) =>
  request.delete(`/datasets/${datasetId}/categories/${encodeURIComponent(name)}`)
export const listCategoryImages = (datasetId, name) =>
  request.get(`/datasets/${datasetId}/categories/${encodeURIComponent(name)}/images`)
export const uploadCategoryImage = (datasetId, name, file) => {
  const formData = new FormData()
  formData.append('file', file)
  return request.post(`/datasets/${datasetId}/categories/${encodeURIComponent(name)}/images`, formData)
}
export const deleteCategoryImage = (datasetId, name, filename) =>
  request.delete(
    `/datasets/${datasetId}/categories/${encodeURIComponent(name)}/images/${encodeURIComponent(filename)}`
  )
