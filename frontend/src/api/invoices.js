import { apiRequest } from './client';

export async function uploadInvoiceFile(file) {
  const formData = new FormData();
  formData.append('file', file);

  return apiRequest('/api/invoices/upload', {
    method: 'POST',
    body: formData,
  });
}

export async function createInvoice(invoiceData) {
  return apiRequest('/api/invoices/', {
    method: 'POST',
    body: JSON.stringify(invoiceData),
  });
}

export async function getInvoices(params = {}) {
  const query = new URLSearchParams();
  if (params.search) query.append('search', params.search);
  if (params.vendor) query.append('vendor', params.vendor);
  if (params.payment_status) query.append('payment_status', params.payment_status);
  if (params.due_date_from) query.append('due_date_from', params.due_date_from);
  if (params.due_date_to) query.append('due_date_to', params.due_date_to);
  if (params.sort_by) query.append('sort_by', params.sort_by);
  if (params.sort_order) query.append('sort_order', params.sort_order);
  if (params.page) query.append('page', params.page.toString());
  if (params.per_page) query.append('per_page', params.per_page.toString());

  const queryString = query.toString() ? `?${query.toString()}` : '';
  return apiRequest(`/api/invoices/${queryString}`, {
    method: 'GET',
  });
}

export async function getInvoice(id) {
  return apiRequest(`/api/invoices/${id}`, {
    method: 'GET',
  });
}

export async function updateInvoice(id, invoiceData) {
  return apiRequest(`/api/invoices/${id}`, {
    method: 'PUT',
    body: JSON.stringify(invoiceData),
  });
}

export async function deleteInvoice(id) {
  return apiRequest(`/api/invoices/${id}`, {
    method: 'DELETE',
  });
}
