import { apiRequest } from './client';

export async function runAssessment() {
  return apiRequest('/api/anomalies/assess', {
    method: 'POST',
  });
}

export async function getAnomalies(params = {}) {
  const query = new URLSearchParams();
  if (params.status) query.append('status', params.status);
  if (params.search) query.append('search', params.search);

  const queryString = query.toString() ? `?${query.toString()}` : '';
  return apiRequest(`/api/anomalies/${queryString}`, {
    method: 'GET',
  });
}

export async function getInvoiceAnomaly(invoiceId) {
  return apiRequest(`/api/anomalies/invoice/${invoiceId}`, {
    method: 'GET',
  });
}

export async function markAnomalyReviewed(anomalyId, reviewNotes = '') {
  return apiRequest(`/api/anomalies/${anomalyId}/review`, {
    method: 'PATCH',
    body: JSON.stringify({ review_notes: reviewNotes }),
  });
}

export async function unmarkAnomalyReviewed(anomalyId) {
  return apiRequest(`/api/anomalies/${anomalyId}/review`, {
    method: 'DELETE',
  });
}
