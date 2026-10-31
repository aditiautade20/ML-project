import { apiRequest, API_BASE_URL } from './client';

export async function previewReconciliationFile(file, fileType = 'LEDGER') {
  const formData = new FormData();
  formData.append('file', file);
  return apiRequest(`/api/reconciliation/preview?file_type=${fileType}`, {
    method: 'POST',
    body: formData,
  });
}

export async function runLedgerReconciliation(file, columnMapping, tolerance = 0.05) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('column_mapping', JSON.stringify(columnMapping));
  formData.append('amount_tolerance', tolerance.toString());

  return apiRequest('/api/reconciliation/run-ledger', {
    method: 'POST',
    body: formData,
  });
}

export async function runBankReconciliation(file, columnMapping, tolerance = 0.05) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('column_mapping', JSON.stringify(columnMapping));
  formData.append('amount_tolerance', tolerance.toString());

  return apiRequest('/api/reconciliation/run-bank', {
    method: 'POST',
    body: formData,
  });
}

export async function runCombinedReconciliation(
  ledgerFile,
  bankFile,
  ledgerMapping,
  bankMapping,
  tolerance = 0.05
) {
  const formData = new FormData();
  formData.append('ledger_file', ledgerFile);
  formData.append('bank_file', bankFile);
  formData.append('ledger_column_mapping', JSON.stringify(ledgerMapping));
  formData.append('bank_column_mapping', JSON.stringify(bankMapping));
  formData.append('amount_tolerance', tolerance.toString());

  return apiRequest('/api/reconciliation/run-combined', {
    method: 'POST',
    body: formData,
  });
}

export async function getReconciliationBatches(limit = 50, skip = 0) {
  return apiRequest(`/api/reconciliation/batches?limit=${limit}&skip=${skip}`, {
    method: 'GET',
  });
}

export async function getReconciliationBatch(batchId) {
  return apiRequest(`/api/reconciliation/batches/${batchId}`, {
    method: 'GET',
  });
}

export async function updateReconciliationItem(batchId, itemId, payload) {
  return apiRequest(`/api/reconciliation/batches/${batchId}/items/${itemId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function confirmBankPayment(batchId, itemId, payload) {
  return apiRequest(`/api/reconciliation/batches/${batchId}/items/${itemId}/confirm-payment`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function deleteReconciliationBatch(batchId) {
  return apiRequest(`/api/reconciliation/batches/${batchId}`, {
    method: 'DELETE',
  });
}

export async function downloadReconciliationCsv(batchId, defaultFilename = 'reconciliation_audit.csv') {
  const token = sessionStorage.getItem('invoiceiq_token') || localStorage.getItem('token');
  const headers = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const endpoint = `${API_BASE_URL}/api/reconciliation/batches/${batchId}/export-csv`;
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
  a.remove();
  window.URL.revokeObjectURL(blobUrl);
}
