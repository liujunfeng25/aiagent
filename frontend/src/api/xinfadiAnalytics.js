import request from './request'

export const getAnalyticsDates = () => request.get('/xinfadi/analytics/dates')

export const getMarketSentiment = () => request.get('/xinfadi/analytics/sentiment')

export const getProductHints = (params) => request.get('/xinfadi/analytics/products', { params })

export const getTimeseries = (params) =>
  request.get('/xinfadi/analytics/timeseries', {
    params: {
      start_date: params.start_date,
      end_date: params.end_date,
      prod_names: Array.isArray(params.prod_names) ? params.prod_names.join(',') : params.prod_names,
      cat1: params.cat1 || '',
    },
  })

export const postBackfill = (body) => request.post('/xinfadi/backfill', body)

export const getBackfillStatus = () => request.get('/xinfadi/backfill/status')

export const postBackfillDismiss = () => request.post('/xinfadi/backfill/dismiss')
