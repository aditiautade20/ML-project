import { apiRequest } from './client';

export async function recordPayment(paymentData) {
  return apiRequest('/api/payments/', {
    method: 'POST',
    body: JSON.stringify(paymentData),
  });
}

export async function getPayments(params = {}) {
  const query = new URLSearchParams();
  if (params.invoice_id) query.append('invoice_id', params.invoice_id.toString());
  if (params.search) query.append('search', params.search);
  if (params.sort_by) query.append('sort_by', params.sort_by);
  if (params.sort_order) query.append('sort_order', params.sort_order);
  if (params.page) query.append('page', params.page.toString());
  if (params.per_page) query.append('per_page', params.per_page.toString());

  const queryString = query.toString() ? `?${query.toString()}` : '';
  return apiRequest(`/api/payments/${queryString}`, {
    method: 'GET',
  });
}

export async function getPayment(id) {
  return apiRequest(`/api/payments/${id}`, {
    method: 'GET',
  });
}

export async function updatePayment(id, paymentData) {
  return apiRequest(`/api/payments/${id}`, {
    method: 'PUT',
    body: JSON.stringify(paymentData),
  });
}

export async function deletePayment(id) {
  return apiRequest(`/api/payments/${id}`, {
    method: 'DELETE',
  });
}

export async function getInvoicePaymentSummary(invoiceId) {
  return apiRequest(`/api/payments/invoice/${invoiceId}/summary`, {
    method: 'GET',
  });
}

export async function getDeadlinesSummary() {
  return apiRequest('/api/invoices/deadlines/summary', {
    method: 'GET',
  });
}
