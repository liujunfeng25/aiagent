import request from './request'

export const getStats = () => request.get('/dashboard/stats')
export const getTrainTrend = () => request.get('/dashboard/train_trend')
export const getTopModels = () => request.get('/dashboard/top_models')
export const getRecentTasks = () => request.get('/dashboard/recent_tasks')
