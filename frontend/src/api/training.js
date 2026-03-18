import request from './request'

export const listTasks = () => request.get('/training/tasks')
export const createTask = (data) => request.post('/training/tasks', data)
export const getTaskStatus = (id) => request.get(`/training/tasks/${id}/status`)
export const deleteTask = (id) => request.delete(`/training/tasks/${id}`)
export const getDatasetSinceLast = (datasetId) => request.get(`/training/dataset/${datasetId}/since-last`)
