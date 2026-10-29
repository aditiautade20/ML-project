import { apiRequest } from './client';

export async function getDashboardAnalytics() {
  return apiRequest('/api/reports/dashboard', {
    method: 'GET',
  });
}

export async function getReportsAnalytics(params = {}) {
  const query = new URLSearchParams();
  if (params.start_date) query.append('start_date', params.start_date);
  if (params.end_date) query.append('end_date', params.end_date);
  if (params.vendor) query.append('vendor', params.vendor);

  const queryString = query.toString() ? `?${query.toString()}` : '';
  return apiRequest(`/api/reports/analytics${queryString}`, {
    method: 'GET',
  });
}

/**
 * Downloads a file from an authenticated endpoint by acquiring a blob
 * and triggering browser download.
 */
async function downloadAuthenticatedFile(endpoint, defaultFilename) {
  const token = localStorage.getItem('token');
  const headers = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(endpoint, {
    method: 'GET',
    headers,
  });

  if (!response.ok) {
    let errorDetail = 'Download failed.';
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errorDetail;
    } catch {
      // fallback
    }
    throw new Error(errorDetail);
  }

  const blob = await response.blob();
  const disposition = response.headers.get('Content-Disposition');
  let filename = defaultFilename;
  if (disposition && disposition.includes('filename=')) {
    const match = disposition.match(/filename="?([^"]+)"?/);
    if (match && match[1]) {
      filename = match[1];
    }
  }

  const blobUrl = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = blobUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(blobUrl);
}

export async function downloadInvoicesCsv(params = {}) {
  const query = new URLSearchParams();
  if (params.start_date) query.append('start_date', params.start_date);
  if (params.end_date) query.append('end_date', params.end_date);
  if (params.vendor) query.append('vendor', params.vendor);
  const q = query.toString() ? `?${query.toString()}` : '';
  return downloadAuthenticatedFile(`/api/reports/export/invoices${q}`, 'invoiceiq_invoices.csv');
}

export async function downloadPaymentsCsv(params = {}) {
  const query = new URLSearchParams();
  if (params.start_date) query.append('start_date', params.start_date);
  if (params.end_date) query.append('end_date', params.end_date);
  if (params.vendor) query.append('vendor', params.vendor);
  const q = query.toString() ? `?${query.toString()}` : '';
  return downloadAuthenticatedFile(`/api/reports/export/payments${q}`, 'invoiceiq_payments.csv');
}

export async function downloadOutstandingCsv(params = {}) {
  const query = new URLSearchParams();
  if (params.start_date) query.append('start_date', params.start_date);
  if (params.end_date) query.append('end_date', params.end_date);
  if (params.vendor) query.append('vendor', params.vendor);
  const q = query.toString() ? `?${query.toString()}` : '';
  return downloadAuthenticatedFile(`/api/reports/export/outstanding${q}`, 'invoiceiq_outstanding.csv');
}

export async function downloadReconciliationCsv(params = {}) {
  const query = new URLSearchParams();
  if (params.start_date) query.append('start_date', params.start_date);
  if (params.end_date) query.append('end_date', params.end_date);
  if (params.vendor) query.append('vendor', params.vendor);
  const q = query.toString() ? `?${query.toString()}` : '';
  return downloadAuthenticatedFile(`/api/reports/export/reconciliation${q}`, 'invoiceiq_reconciliation.csv');
}

export async function downloadReportPdf(params = {}) {
  const query = new URLSearchParams();
  if (params.start_date) query.append('start_date', params.start_date);
  if (params.end_date) query.append('end_date', params.end_date);
  if (params.vendor) query.append('vendor', params.vendor);
  const q = query.toString() ? `?${query.toString()}` : '';
  return downloadAuthenticatedFile(`/api/reports/export/pdf${q}`, 'invoiceiq_report.pdf');
}
