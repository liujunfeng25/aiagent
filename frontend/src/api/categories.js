import request from './request'

export const listCategories = () => request.get('/categories/')
export const createCategory = (data) => request.post('/categories/', data)
export const deleteCategory = (name) => request.delete(`/categories/${encodeURIComponent(name)}`)
export const listImages = (name) => request.get(`/categories/${encodeURIComponent(name)}/images`)
export const uploadImage = (name, file) => {
  const formData = new FormData()
  formData.append('file', file)
  return request.post(`/categories/${encodeURIComponent(name)}/images`, formData)
}
export const deleteImage = (name, filename) =>
  request.delete(`/categories/${encodeURIComponent(name)}/images/${encodeURIComponent(filename)}`)
export const trainFromCategories = (data) => request.post('/categories/train', data)
