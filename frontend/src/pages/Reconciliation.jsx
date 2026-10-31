import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Scale,
  Upload,
  FileSpreadsheet,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  Clock,
  ArrowRight,
  Filter,
  Download,
  Trash2,
  Eye,
  Check,
  X,
  RefreshCw,
  Search,
  Sliders,
  ShieldCheck,
  HelpCircle,
  Building,
  Table,
  Info,
  ChevronRight,
  ExternalLink,
} from 'lucide-react';
import {
  previewReconciliationFile,
  runLedgerReconciliation,
  getReconciliationBatches,
  getReconciliationBatch,
  updateReconciliationItem,
  deleteReconciliationBatch,
  downloadReconciliationCsv,
} from '../api/reconciliation';

function formatCurrency(amount, currency = 'USD') {
  const num = typeof amount === 'number' ? amount : parseFloat(amount || 0);
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency || 'USD',
      minimumFractionDigits: 2,
    }).format(num);
  } catch {
    return `$${num.toFixed(2)}`;
  }
}

function MappingStatusBadge({ status, value }) {
  const currentStatus = status || (value ? 'USER_SELECTED' : 'UNMAPPED');
  if (currentStatus === 'AUTO_MAPPED') {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">
        <Check className="w-3 h-3 mr-1 text-emerald-600" /> Auto-mapped
      </span>
    );
  }
  if (currentStatus === 'NEEDS_CONFIRMATION') {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-100 text-amber-800 border border-amber-300">
        <AlertTriangle className="w-3 h-3 mr-1 text-amber-600" /> Confirm
      </span>
    );
  }
  if (currentStatus === 'USER_SELECTED') {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-100 text-blue-800 border border-blue-200">
        <Check className="w-3 h-3 mr-1 text-blue-600" /> Selected
      </span>
    );
  }
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-slate-100 text-slate-500 border border-slate-200">
      Unmapped
    </span>
  );
}

function ColumnMappingField({
  label,
  fieldKey,
  required = false,
  value,
  status,
  warning,
  candidates = [],
  headers = [],
  onChange,
  onSelectCandidate,
}) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between mb-1">
        <label className="block text-xs font-semibold text-slate-700">
          {label} {required && <span className="text-rose-500 font-bold">*</span>}
        </label>
        <MappingStatusBadge status={status} value={value} />
      </div>
      <select
        value={value || ''}
        onChange={(e) => onChange(fieldKey, e.target.value)}
        className={`w-full text-xs border rounded p-2 bg-white transition-colors focus:ring-teal-500 focus:border-teal-500 ${
          status === 'NEEDS_CONFIRMATION'
            ? 'border-amber-400 bg-amber-50/30'
            : status === 'AUTO_MAPPED'
            ? 'border-emerald-300'
            : 'border-slate-300'
        }`}
      >
        <option value="">{required ? '-- Select Column --' : '-- (Optional) --'}</option>
        {headers.map((h) => (
          <option key={h} value={h}>
            {h}
          </option>
        ))}
      </select>
      {warning && (
        <div className="mt-1 text-[11px] text-amber-800 bg-amber-50 border border-amber-200 rounded p-1.5 flex items-start space-x-1.5">
          <AlertCircle className="w-3.5 h-3.5 text-amber-600 shrink-0 mt-0.5" />
          <div className="flex-1 leading-tight">{warning}</div>
        </div>
      )}
      {candidates && candidates.length > 1 && (
        <div className="flex items-center flex-wrap gap-1 pt-1">
          <span className="text-[10px] text-slate-500 font-medium">Suggestions:</span>
          {candidates.map((cand) => (
            <button
              key={cand}
              type="button"
              onClick={() => onSelectCandidate(fieldKey, cand)}
              className={`text-[10px] px-1.5 py-0.5 rounded border transition-colors ${
                value === cand
                  ? 'bg-teal-600 text-white border-teal-600 font-semibold'
                  : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-100'
              }`}
            >
              {cand}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// Map backend match_status to the 4 standardized status labels
function getStandardStatus(matchStatus, reviewStatus) {
  if (reviewStatus === 'PENDING' && matchStatus === 'AMBIGUOUS_MATCH') {
    return {
      key: 'NEEDS_REVIEW',
      label: 'Needs Review',
      badgeClass: 'bg-slate-100 text-slate-800 border-slate-300',
      icon: Clock,
    };
  }
  if (matchStatus === 'EXACT_MATCH' || matchStatus === 'MATCHED' || matchStatus === 'MATCH') {
    return {
      key: 'MATCHED',
      label: 'Matched',
      badgeClass: 'bg-emerald-50 text-emerald-800 border-emerald-300',
      icon: CheckCircle2,
    };
  }
  if (
    matchStatus === 'AMOUNT_MISMATCH' ||
    matchStatus === 'TAX_MISMATCH' ||
    matchStatus === 'DATE_MISMATCH' ||
    matchStatus === 'MISMATCH' ||
    matchStatus === 'DUPLICATE_SUSPECTED'
  ) {
    return {
      key: 'MISMATCH',
      label: 'Mismatch',
      badgeClass: 'bg-amber-50 text-amber-800 border-amber-300',
      icon: AlertTriangle,
    };
  }
  if (
    matchStatus === 'MISSING_IN_LEDGER' ||
    matchStatus === 'MISSING_IN_INVOICES' ||
    matchStatus === 'MISSING_IN_FILE' ||
    matchStatus === 'UNMATCHED_INVOICE' ||
    matchStatus === 'UNMATCHED_LEDGER_RECORD' ||
    matchStatus === 'UNMATCHED_BANK_TXN'
  ) {
    return {
      key: 'UNMATCHED',
      label: 'Unmatched',
      badgeClass: 'bg-rose-50 text-rose-800 border-rose-300',
      icon: AlertCircle,
    };
  }
  return {
    key: 'NEEDS_REVIEW',
    label: 'Needs Review',
    badgeClass: 'bg-slate-100 text-slate-800 border-slate-300',
    icon: HelpCircle,
  };
}

export default function Reconciliation() {
  const navigate = useNavigate();

  // Navigation: Only 2 options
  // 'RECORDS' = Option 1: Ledger Records
  // 'RECONCILIATION' = Option 2: Reconciliation
  const [activeTab, setActiveTab] = useState('RECORDS');

  // Batches and Active Batch
  const [batches, setBatches] = useState([]);
  const [currentBatch, setCurrentBatch] = useState(null);

  // Loading & Message States
  const [isLoading, setIsLoading] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  // Matching Tolerance (default ±$0.05)
  const [amountTolerance, setAmountTolerance] = useState(0.05);

  // Option 1: Ledger Records State
  const [ledgerFile, setLedgerFile] = useState(null);
  const [ledgerPreview, setLedgerPreview] = useState(null);
  const [ledgerMapping, setLedgerMapping] = useState({});
  const [ledgerMappingStatuses, setLedgerMappingStatuses] = useState({});
  const [ledgerMappingWarnings, setLedgerMappingWarnings] = useState({});
  const [ledgerAmbiguousColumns, setLedgerAmbiguousColumns] = useState({});
  const [ledgerSearch, setLedgerSearch] = useState('');

  // Option 2: Reconciliation Filtering
  const [itemSearch, setItemSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL'); // 'ALL' | 'MATCHED' | 'MISMATCH' | 'UNMATCHED' | 'NEEDS_REVIEW'

  // Fetch batches on mount
  const loadBatches = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage('');
    try {
      const data = await getReconciliationBatches();
      setBatches(data || []);
      // If there's an existing batch and no batch currently selected, optionally prepare it
      if (data && data.length > 0 && !currentBatch) {
        // keep currentBatch null initially so user sees upload / records first
      }
    } catch (err) {
      setErrorMessage(err.message || 'Failed to fetch reconciliation history.');
    } finally {
      setIsLoading(false);
    }
  }, [currentBatch]);

  useEffect(() => {
    loadBatches();
  }, [loadBatches]);

  // Handle Ledger File Selection
  const handleLedgerFileChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLedgerFile(file);
    setErrorMessage('');
    setSuccessMessage('');
    try {
      const prev = await previewReconciliationFile(file, 'LEDGER');
      setLedgerPreview(prev);
      setLedgerMapping(prev.suggested_mapping || {});
      setLedgerMappingStatuses(prev.mapping_statuses || {});
      setLedgerMappingWarnings(prev.mapping_warnings || {});
      setLedgerAmbiguousColumns(prev.ambiguous_columns || {});
      setSuccessMessage(`File "${file.name}" loaded: ${prev.total_rows} rows detected.`);
    } catch (err) {
      setErrorMessage(`Failed to parse ledger file: ${err.message}`);
      setLedgerFile(null);
      setLedgerPreview(null);
      setLedgerMapping({});
      setLedgerMappingStatuses({});
      setLedgerMappingWarnings({});
      setLedgerAmbiguousColumns({});
    }
  };

  const handleLedgerFieldChange = (field, value) => {
    setLedgerMapping((m) => ({ ...m, [field]: value }));
    setLedgerMappingStatuses((s) => ({
      ...s,
      [field]: value ? 'USER_SELECTED' : 'UNMAPPED',
    }));
    setLedgerMappingWarnings((w) => {
      const copy = { ...w };
      delete copy[field];
      return copy;
    });
  };

  // Run Invoice-to-Ledger Reconciliation
  const handleRunLedger = async () => {
    if (!ledgerFile) return;

    // Check basic validation
    if (!ledgerMapping.invoice_number && !ledgerMapping.total_amount) {
      setErrorMessage('Please map Voucher/Invoice Number and Total Amount before running reconciliation.');
      return;
    }

    setIsProcessing(true);
    setErrorMessage('');
    setSuccessMessage('');
    try {
      const res = await runLedgerReconciliation(ledgerFile, ledgerMapping, amountTolerance);
      setCurrentBatch(res);
      setSuccessMessage(
        `Reconciliation completed: ${res.exact_matches} matched, ${res.mismatches} mismatches, ${res.unmatched_records} unmatched records.`
      );
      loadBatches();
      // Automatically switch to Reconciliation tab to display results
      setActiveTab('RECONCILIATION');
    } catch (err) {
      setErrorMessage(err.message || 'Failed to execute ledger reconciliation.');
    } finally {
      setIsProcessing(false);
    }
  };

  // Select a historical batch to inspect
  const handleSelectBatch = async (batchId) => {
    setIsLoading(true);
    setErrorMessage('');
    try {
      const b = await getReconciliationBatch(batchId);
      setCurrentBatch(b);
      setActiveTab('RECONCILIATION');
    } catch (err) {
      setErrorMessage(err.message || 'Failed to load batch records.');
    } finally {
      setIsLoading(false);
    }
  };

  // Delete a batch
  const handleDeleteBatch = async (batchId, e) => {
    e.stopPropagation();
    if (!window.confirm('Are you sure you want to delete this reconciliation batch?')) return;
    try {
      await deleteReconciliationBatch(batchId);
      if (currentBatch?.id === batchId) {
        setCurrentBatch(null);
      }
      setSuccessMessage('Batch deleted successfully.');
      loadBatches();
    } catch (err) {
      setErrorMessage(err.message || 'Failed to delete batch.');
    }
  };

  // Update Item Review Status
  const handleStatusChange = async (itemId, newStatus) => {
    try {
      await updateReconciliationItem(currentBatch.id, itemId, {
        review_status: newStatus,
      });
      setCurrentBatch((b) => ({
        ...b,
        items: b.items.map((it) => (it.id === itemId ? { ...it, review_status: newStatus } : it)),
      }));
    } catch (err) {
      setErrorMessage(err.message || 'Failed to update item review status.');
    }
  };

  // Export CSV
  const handleExportCsv = async () => {
    if (!currentBatch) return;
    try {
      await downloadReconciliationCsv();
      setSuccessMessage('Reconciliation audit CSV exported successfully.');
      setTimeout(() => setSuccessMessage(''), 4000);
    } catch (err) {
      setErrorMessage(err.message || 'Failed to export CSV.');
    }
  };

  // Filtered Reconciliation Items
  const filteredItems = useMemo(() => {
    if (!currentBatch?.items) return [];
    return currentBatch.items.filter((item) => {
      // 1. Text search
      if (itemSearch.trim()) {
        const q = itemSearch.toLowerCase().trim();
        const idMatch = (item.record_identifier || '').toLowerCase().includes(q);
        const cpMatch = (item.vendor_or_counterparty || '').toLowerCase().includes(q);
        const evMatch = (item.evidence_text || '').toLowerCase().includes(q);
        if (!idMatch && !cpMatch && !evMatch) return false;
      }

      // 2. Status filter
      if (statusFilter === 'ALL') return true;
      const std = getStandardStatus(item.match_status, item.review_status);
      return std.key === statusFilter;
    });
  }, [currentBatch, itemSearch, statusFilter]);

  // Reconciliation summary counts
  const reconCounts = useMemo(() => {
    if (!currentBatch?.items) {
      return { total: 0, matched: 0, mismatch: 0, unmatched: 0, needsReview: 0 };
    }
    let matched = 0;
    let mismatch = 0;
    let unmatched = 0;
    let needsReview = 0;

    currentBatch.items.forEach((item) => {
      const std = getStandardStatus(item.match_status, item.review_status);
      if (std.key === 'MATCHED') matched++;
      else if (std.key === 'MISMATCH') mismatch++;
      else if (std.key === 'UNMATCHED') unmatched++;
      else if (std.key === 'NEEDS_REVIEW') needsReview++;
    });

    return {
      total: currentBatch.items.length,
      matched,
      mismatch,
      unmatched,
      needsReview,
    };
  }, [currentBatch]);

  // Filtered Preview Rows for Option 1
  const filteredSampleRows = useMemo(() => {
    if (!ledgerPreview?.sample_rows) return [];
    if (!ledgerSearch.trim()) return ledgerPreview.sample_rows;
    const q = ledgerSearch.toLowerCase().trim();
    return ledgerPreview.sample_rows.filter((row) =>
      Object.values(row).some((val) => String(val).toLowerCase().includes(q))
    );
  }, [ledgerPreview, ledgerSearch]);

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center space-x-2">
            <Scale className="w-6 h-6 text-teal-600" />
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Ledger & Reconciliation</h1>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            Manage accounting ledger records and compare transactions against saved invoices.
          </p>
        </div>

        {/* Global Action Toolbar */}
        <div className="flex items-center space-x-2.5">
          {currentBatch && (
            <button
              onClick={handleExportCsv}
              className="inline-flex items-center px-3.5 py-2 border border-slate-300 shadow-xs text-xs font-semibold rounded-md text-slate-700 bg-white hover:bg-slate-50 transition-colors"
            >
              <Download className="w-3.5 h-3.5 mr-1.5 text-slate-500" />
              Export Audit CSV
            </button>
          )}

          <button
            onClick={() => {
              setActiveTab('RECORDS');
              setLedgerFile(null);
              setLedgerPreview(null);
              setLedgerMapping({});
            }}
            className="inline-flex items-center px-3.5 py-2 border border-transparent shadow-xs text-xs font-semibold rounded-md text-white bg-teal-600 hover:bg-teal-700 transition-colors"
          >
            <Upload className="w-3.5 h-3.5 mr-1.5" />
            Upload Ledger File
          </button>
        </div>
      </div>

      {/* Notifications */}
      {errorMessage && (
        <div className="p-3.5 rounded-md bg-rose-50 border border-rose-200 flex items-start space-x-3 text-xs text-rose-800">
          <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
          <div className="flex-1">{errorMessage}</div>
          <button onClick={() => setErrorMessage('')} className="text-rose-500 hover:text-rose-700">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}
      {successMessage && (
        <div className="p-3.5 rounded-md bg-emerald-50 border border-emerald-200 flex items-start space-x-3 text-xs text-emerald-800">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
          <div className="flex-1">{successMessage}</div>
          <button onClick={() => setSuccessMessage('')} className="text-emerald-500 hover:text-emerald-700">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Simplified Navigation (ONLY TWO OPTIONS) */}
      <div className="border-b border-slate-200">
        <nav className="flex space-x-8">
          <button
            onClick={() => setActiveTab('RECORDS')}
            className={`py-3 px-1 border-b-2 text-xs font-bold inline-flex items-center space-x-2 transition-colors whitespace-nowrap ${
              activeTab === 'RECORDS'
                ? 'border-teal-600 text-teal-700'
                : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'
            }`}
          >
            <FileSpreadsheet className="w-4 h-4" />
            <span>1. Ledger Records</span>
            {ledgerPreview && (
              <span className="px-1.5 py-0.2 rounded-full bg-teal-100 text-teal-800 text-[10px] font-mono">
                {ledgerPreview.total_rows}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab('RECONCILIATION')}
            className={`py-3 px-1 border-b-2 text-xs font-bold inline-flex items-center space-x-2 transition-colors whitespace-nowrap ${
              activeTab === 'RECONCILIATION'
                ? 'border-teal-600 text-teal-700'
                : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'
            }`}
          >
            <Scale className="w-4 h-4" />
            <span>2. Reconciliation</span>
            {currentBatch && (
              <span className="px-1.5 py-0.2 rounded-full bg-slate-100 text-slate-700 text-[10px] font-mono">
                Batch #{currentBatch.id}
              </span>
            )}
          </button>
        </nav>
      </div>

      {/* OPTION 1: LEDGER RECORDS */}
      {activeTab === 'RECORDS' && (
        <div className="space-y-6">
          {/* Guide Banner */}
          <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 text-xs text-slate-700 flex items-start gap-3">
            <Info className="w-4 h-4 text-teal-600 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <span className="font-bold text-slate-900 block">Option 1: Accounting Ledger Records</span>
              <p className="text-slate-600 leading-relaxed">
                Upload General Ledger exports (.CSV or Excel .XLSX). Verify extracted transaction fields
                (voucher number, posting date, description, debit, credit, amount) and resolve any column mapping warnings before reconciling with invoices.
              </p>
            </div>
          </div>

          {/* Upload Dropzone */}
          {!ledgerPreview ? (
            <div className="bg-white rounded-lg border-2 border-dashed border-slate-300 p-8 text-center hover:border-teal-500 transition-colors shadow-xs">
              <FileSpreadsheet className="w-12 h-12 mx-auto text-slate-400 mb-3" />
              <label htmlFor="ledger-upload-input" className="cursor-pointer">
                <span className="text-sm font-semibold text-teal-600 hover:text-teal-700 block mb-1">
                  Click to select accounting ledger file (.CSV or .XLSX)
                </span>
                <span className="text-xs text-slate-500">Supports standard ledger exports with voucher, debit, credit, and totals</span>
                <input
                  id="ledger-upload-input"
                  type="file"
                  accept=".csv, .xlsx, .xls"
                  className="hidden"
                  onClick={(e) => {
                    e.target.value = null;
                  }}
                  onChange={handleLedgerFileChange}
                />
              </label>
              <p className="text-[11px] text-slate-400 mt-3">Maximum file size 10MB • Preserves existing database</p>
            </div>
          ) : (
            <div className="space-y-6">
              {/* File Header Bar */}
              <div className="flex items-center justify-between p-4 bg-teal-50 border border-teal-200 rounded-lg text-xs">
                <div className="flex items-center space-x-3">
                  <div className="w-8 h-8 rounded bg-teal-600 text-white flex items-center justify-center font-bold">
                    GL
                  </div>
                  <div>
                    <span className="font-bold text-slate-900 block text-sm">{ledgerPreview.filename}</span>
                    <span className="text-teal-800">
                      {ledgerPreview.total_rows} records detected • Format: {ledgerPreview.file_type}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      setLedgerFile(null);
                      setLedgerPreview(null);
                      setLedgerMapping({});
                    }}
                    className="px-3 py-1.5 bg-white border border-slate-300 hover:bg-slate-100 text-slate-700 rounded font-medium transition-colors"
                  >
                    Change File
                  </button>

                  <button
                    onClick={handleRunLedger}
                    disabled={isProcessing}
                    className="inline-flex items-center gap-1.5 px-4 py-1.5 bg-teal-600 hover:bg-teal-700 text-white rounded font-semibold transition-colors shadow-xs disabled:opacity-50"
                  >
                    {isProcessing ? (
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Scale className="w-3.5 h-3.5" />
                    )}
                    <span>Reconcile with Invoices &rarr;</span>
                  </button>
                </div>
              </div>

              {/* Column Mapping & Validation Errors Panel */}
              <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-xs space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                  <div>
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                      Column Mapping & Field Validation
                    </h3>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Verify mapped columns. Basic validation checks ensure voucher numbers and amounts are present.
                    </p>
                  </div>
                  <div className="flex items-center space-x-2 text-xs">
                    <MappingStatusBadge status="AUTO_MAPPED" />
                    <MappingStatusBadge status="NEEDS_CONFIRMATION" />
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
                  <ColumnMappingField
                    label="Voucher / Reference / Invoice #"
                    fieldKey="invoice_number"
                    required
                    value={ledgerMapping.invoice_number}
                    status={ledgerMappingStatuses.invoice_number}
                    warning={ledgerMappingWarnings.invoice_number}
                    candidates={ledgerAmbiguousColumns.invoice_number}
                    headers={ledgerPreview.headers || []}
                    onChange={handleLedgerFieldChange}
                    onSelectCandidate={handleLedgerFieldChange}
                  />

                  <ColumnMappingField
                    label="Total / Transaction Amount"
                    fieldKey="total_amount"
                    required
                    value={ledgerMapping.total_amount}
                    status={ledgerMappingStatuses.total_amount}
                    warning={ledgerMappingWarnings.total_amount}
                    candidates={ledgerAmbiguousColumns.total_amount}
                    headers={ledgerPreview.headers || []}
                    onChange={handleLedgerFieldChange}
                    onSelectCandidate={handleLedgerFieldChange}
                  />

                  <ColumnMappingField
                    label="Debit Column"
                    fieldKey="debit_column"
                    value={ledgerMapping.debit_column}
                    status={ledgerMappingStatuses.debit_column}
                    warning={ledgerMappingWarnings.debit_column}
                    candidates={ledgerAmbiguousColumns.debit_column}
                    headers={ledgerPreview.headers || []}
                    onChange={handleLedgerFieldChange}
                    onSelectCandidate={handleLedgerFieldChange}
                  />

                  <ColumnMappingField
                    label="Credit Column"
                    fieldKey="credit_column"
                    value={ledgerMapping.credit_column}
                    status={ledgerMappingStatuses.credit_column}
                    warning={ledgerMappingWarnings.credit_column}
                    candidates={ledgerAmbiguousColumns.credit_column}
                    headers={ledgerPreview.headers || []}
                    onChange={handleLedgerFieldChange}
                    onSelectCandidate={handleLedgerFieldChange}
                  />

                  <ColumnMappingField
                    label="Description / Particulars / Payee"
                    fieldKey="vendor_name"
                    value={ledgerMapping.vendor_name}
                    status={ledgerMappingStatuses.vendor_name}
                    warning={ledgerMappingWarnings.vendor_name}
                    candidates={ledgerAmbiguousColumns.vendor_name}
                    headers={ledgerPreview.headers || []}
                    onChange={handleLedgerFieldChange}
                    onSelectCandidate={handleLedgerFieldChange}
                  />

                  <ColumnMappingField
                    label="Posting Date / Date"
                    fieldKey="invoice_date"
                    value={ledgerMapping.invoice_date}
                    status={ledgerMappingStatuses.invoice_date}
                    warning={ledgerMappingWarnings.invoice_date}
                    candidates={ledgerAmbiguousColumns.invoice_date}
                    headers={ledgerPreview.headers || []}
                    onChange={handleLedgerFieldChange}
                    onSelectCandidate={handleLedgerFieldChange}
                  />
                </div>
              </div>

              {/* View Uploaded Ledger Entries Table */}
              <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-xs space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
                  <div>
                    <h3 className="text-sm font-bold text-slate-900">
                      Uploaded Ledger Entries ({ledgerPreview.sample_rows?.length || 0} sample rows)
                    </h3>
                    <p className="text-xs text-slate-500">
                      Review parsed accounting records before comparing against invoices.
                    </p>
                  </div>

                  <input
                    type="text"
                    placeholder="Search in ledger entries..."
                    value={ledgerSearch}
                    onChange={(e) => setLedgerSearch(e.target.value)}
                    className="px-2.5 py-1 border border-slate-200 rounded text-xs text-slate-800 placeholder-slate-400 w-56"
                  />
                </div>

                <div className="overflow-x-auto border border-slate-200 rounded-md">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
                      <tr>
                        {(ledgerPreview.headers || []).map((h) => (
                          <th key={h} className="py-2.5 px-3 whitespace-nowrap">
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
                      {filteredSampleRows.length === 0 ? (
                        <tr>
                          <td
                            colSpan={ledgerPreview.headers?.length || 1}
                            className="py-8 text-center text-slate-400 font-sans"
                          >
                            No entries found matching search.
                          </td>
                        </tr>
                      ) : (
                        filteredSampleRows.map((row, rIdx) => (
                          <tr key={rIdx} className="hover:bg-slate-50/80">
                            {(ledgerPreview.headers || []).map((h) => (
                              <td key={h} className="py-2 px-3 whitespace-nowrap text-slate-700">
                                {row[h] !== undefined && row[h] !== null ? String(row[h]) : '—'}
                              </td>
                            ))}
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>

                <div className="pt-2 flex justify-end">
                  <button
                    onClick={handleRunLedger}
                    disabled={isProcessing}
                    className="inline-flex items-center gap-1.5 px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded text-xs font-semibold transition-colors shadow-xs"
                  >
                    <span>Run Reconciliation with Invoices</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Past Batches History Drawer */}
          {batches.length > 0 && (
            <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-xs space-y-3">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                <div>
                  <h3 className="text-sm font-bold text-slate-900">Historical Ledger Batches</h3>
                  <p className="text-xs text-slate-500">Previously reconciled accounting ledgers</p>
                </div>
                <button
                  onClick={loadBatches}
                  className="text-xs text-teal-600 hover:text-teal-700 font-medium inline-flex items-center"
                >
                  <RefreshCw className="w-3 h-3 mr-1" /> Refresh
                </button>
              </div>

              <div className="divide-y divide-slate-100">
                {batches.map((b) => (
                  <div
                    key={b.id}
                    onClick={() => handleSelectBatch(b.id)}
                    className="py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-slate-50/80 p-2 rounded cursor-pointer transition-colors"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-slate-900 text-xs">{b.title}</span>
                        <span className="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-mono">
                          Batch #{b.id}
                        </span>
                      </div>
                      <span className="text-[11px] text-slate-500">
                        {new Date(b.created_at).toLocaleString()} • {b.total_records} rows processed
                      </span>
                    </div>

                    <div className="flex items-center gap-4 text-xs">
                      <div className="flex items-center gap-3 text-[11px] font-semibold">
                        <span className="text-emerald-700">{b.exact_matches} matched</span>
                        <span className="text-amber-700">{b.mismatches} mismatches</span>
                        <span className="text-rose-700">{b.unmatched_records} unmatched</span>
                      </div>
                      <button
                        onClick={(e) => handleDeleteBatch(b.id, e)}
                        className="text-slate-400 hover:text-rose-600 p-1"
                        title="Delete batch"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* OPTION 2: RECONCILIATION */}
      {activeTab === 'RECONCILIATION' && (
        <div className="space-y-6">
          {/* Guide Banner */}
          <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 text-xs text-slate-700 flex items-start justify-between gap-3">
            <div className="flex items-start gap-3">
              <Scale className="w-4 h-4 text-teal-600 shrink-0 mt-0.5" />
              <div>
                <span className="font-bold text-slate-900 block">Option 2: Invoice-to-Ledger Reconciliation</span>
                <p className="text-slate-600 mt-0.5 leading-relaxed">
                  Cross-examines saved invoices against accounting ledger lines. Discrepancies in totals, taxes, dates, or missing entries are highlighted with clear explanations.
                </p>
              </div>
            </div>

            {/* Tolerance Setting */}
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-[11px] font-semibold text-slate-600">Tolerance:</span>
              <input
                type="number"
                step="0.01"
                min="0.00"
                max="5.00"
                value={amountTolerance}
                onChange={(e) => setAmountTolerance(parseFloat(e.target.value) || 0)}
                className="w-16 px-2 py-0.5 text-xs border border-slate-300 rounded bg-white text-slate-900"
              />
            </div>
          </div>

          {!currentBatch ? (
            /* No Batch Selected State */
            <div className="bg-white border border-slate-200 rounded-lg p-12 text-center shadow-xs">
              <Scale className="w-10 h-10 mx-auto text-slate-300 mb-2" />
              <h3 className="font-bold text-slate-800 text-sm">No Active Reconciliation Batch</h3>
              <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
                Select a historical batch below or upload an accounting ledger file in the Ledger Records section to run a comparison.
              </p>
              <div className="mt-4 flex justify-center gap-2">
                <button
                  onClick={() => setActiveTab('RECORDS')}
                  className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded text-xs font-semibold shadow-xs transition-colors"
                >
                  <Upload className="w-3.5 h-3.5" />
                  <span>Go to Ledger Records &rarr;</span>
                </button>
              </div>

              {batches.length > 0 && (
                <div className="mt-8 text-left border-t border-slate-100 pt-5 max-w-xl mx-auto">
                  <span className="text-xs font-bold text-slate-500 uppercase tracking-wider block mb-2">
                    Or select a past batch:
                  </span>
                  <div className="divide-y divide-slate-100 border border-slate-200 rounded-md">
                    {batches.map((b) => (
                      <div
                        key={b.id}
                        onClick={() => handleSelectBatch(b.id)}
                        className="p-3 hover:bg-slate-50 flex items-center justify-between cursor-pointer text-xs"
                      >
                        <div>
                          <span className="font-bold text-slate-900">{b.title}</span>
                          <span className="text-slate-400 block text-[11px]">
                            {new Date(b.created_at).toLocaleDateString()} • {b.total_records} records
                          </span>
                        </div>
                        <span className="text-teal-600 font-semibold hover:underline">
                          Inspect &rarr;
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            /* Active Reconciliation Results */
            <div className="space-y-6">
              {/* Batch Summary Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-4 border border-slate-200 rounded-lg shadow-xs">
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-sm font-bold text-slate-900">{currentBatch.title}</h2>
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-teal-50 text-teal-800 border border-teal-200">
                      Batch #{currentBatch.id}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Reconciled on {new Date(currentBatch.created_at).toLocaleString()}
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={handleExportCsv}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 rounded text-xs font-semibold shadow-xs transition-colors"
                  >
                    <Download className="w-3.5 h-3.5 text-slate-500" />
                    <span>Export CSV</span>
                  </button>
                  <button
                    onClick={() => setCurrentBatch(null)}
                    className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded text-xs font-semibold transition-colors"
                  >
                    Close Batch
                  </button>
                </div>
              </div>

              {/* 4 Standardized Status Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                {/* 1. Matched */}
                <div
                  onClick={() => setStatusFilter('MATCHED')}
                  className={`bg-white border rounded-lg p-4 shadow-xs cursor-pointer transition-all ${
                    statusFilter === 'MATCHED'
                      ? 'border-emerald-500 ring-2 ring-emerald-200 bg-emerald-50/20'
                      : 'border-slate-200 hover:border-emerald-300'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-600">Matched</span>
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  </div>
                  <span className="text-2xl font-bold text-emerald-700 mt-2 block">
                    {reconCounts.matched}
                  </span>
                  <span className="text-[11px] text-slate-500">Perfect amount & ID match</span>
                </div>

                {/* 2. Mismatch */}
                <div
                  onClick={() => setStatusFilter('MISMATCH')}
                  className={`bg-white border rounded-lg p-4 shadow-xs cursor-pointer transition-all ${
                    statusFilter === 'MISMATCH'
                      ? 'border-amber-500 ring-2 ring-amber-200 bg-amber-50/20'
                      : 'border-slate-200 hover:border-amber-300'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-600">Mismatch</span>
                    <AlertTriangle className="w-4 h-4 text-amber-600" />
                  </div>
                  <span className="text-2xl font-bold text-amber-700 mt-2 block">
                    {reconCounts.mismatch}
                  </span>
                  <span className="text-[11px] text-slate-500">Amount, tax, or date variances</span>
                </div>

                {/* 3. Unmatched */}
                <div
                  onClick={() => setStatusFilter('UNMATCHED')}
                  className={`bg-white border rounded-lg p-4 shadow-xs cursor-pointer transition-all ${
                    statusFilter === 'UNMATCHED'
                      ? 'border-rose-500 ring-2 ring-rose-200 bg-rose-50/20'
                      : 'border-slate-200 hover:border-rose-300'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-600">Unmatched</span>
                    <AlertCircle className="w-4 h-4 text-rose-600" />
                  </div>
                  <span className="text-2xl font-bold text-rose-700 mt-2 block">
                    {reconCounts.unmatched}
                  </span>
                  <span className="text-[11px] text-slate-500">Missing in ledger or invoices</span>
                </div>

                {/* 4. Needs Review */}
                <div
                  onClick={() => setStatusFilter('NEEDS_REVIEW')}
                  className={`bg-white border rounded-lg p-4 shadow-xs cursor-pointer transition-all ${
                    statusFilter === 'NEEDS_REVIEW'
                      ? 'border-slate-500 ring-2 ring-slate-200 bg-slate-50'
                      : 'border-slate-200 hover:border-slate-400'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-600">Needs Review</span>
                    <Clock className="w-4 h-4 text-slate-500" />
                  </div>
                  <span className="text-2xl font-bold text-slate-800 mt-2 block">
                    {reconCounts.needsReview}
                  </span>
                  <span className="text-[11px] text-slate-500">Uncertain or pending review</span>
                </div>
              </div>

              {/* Discrepancy Table Card */}
              <div className="bg-white border border-slate-200 rounded-lg shadow-xs overflow-hidden">
                {/* Filter and Search Bar */}
                <div className="p-4 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                  {/* Status Pills */}
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="font-semibold text-slate-600 mr-1">Status:</span>
                    {['ALL', 'MATCHED', 'MISMATCH', 'UNMATCHED', 'NEEDS_REVIEW'].map((st) => (
                      <button
                        key={st}
                        onClick={() => setStatusFilter(st)}
                        className={`px-2.5 py-1 rounded text-xs transition-colors ${
                          statusFilter === st
                            ? 'bg-teal-600 text-white font-bold shadow-xs'
                            : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                        }`}
                      >
                        {st === 'ALL'
                          ? `All (${currentBatch.items?.length || 0})`
                          : st === 'MATCHED'
                          ? `Matched (${reconCounts.matched})`
                          : st === 'MISMATCH'
                          ? `Mismatch (${reconCounts.mismatch})`
                          : st === 'UNMATCHED'
                          ? `Unmatched (${reconCounts.unmatched})`
                          : `Needs Review (${reconCounts.needsReview})`}
                      </button>
                    ))}
                  </div>

                  {/* Search Box */}
                  <input
                    type="text"
                    placeholder="Search by invoice #, vendor, or evidence..."
                    value={itemSearch}
                    onChange={(e) => setItemSearch(e.target.value)}
                    className="px-2.5 py-1 border border-slate-200 rounded text-xs text-slate-800 placeholder-slate-400 w-64"
                  />
                </div>

                {/* Items Discrepancy Table */}
                {filteredItems.length === 0 ? (
                  <div className="py-12 text-center text-slate-500 text-xs">
                    No reconciliation items found matching filter criteria.
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
                        <tr>
                          <th className="py-3 px-3.5">Record Identifier</th>
                          <th className="py-3 px-3">Supplier / Counterparty</th>
                          <th className="py-3 px-3">Date</th>
                          <th className="py-3 px-3 text-right">Expected (Invoice)</th>
                          <th className="py-3 px-3 text-right">Actual (Ledger)</th>
                          <th className="py-3 px-3 text-right">Difference</th>
                          <th className="py-3 px-3 text-center">Match Status</th>
                          <th className="py-3 px-3.5">Audit Reason & Evidence</th>
                          <th className="py-3 px-3.5 text-right">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {filteredItems.map((item) => {
                          const statusInfo = getStandardStatus(item.match_status, item.review_status);
                          const StatusIcon = statusInfo.icon;
                          const diffNumber = item.discrepancy_amount ? parseFloat(item.discrepancy_amount) : 0;
                          const hasDiff = Math.abs(diffNumber) > 0.001;

                          return (
                            <tr key={item.id} className="hover:bg-slate-50/70 transition-colors">
                              {/* Identifier */}
                              <td className="py-3 px-3.5 font-semibold text-slate-900 whitespace-nowrap">
                                <div className="flex items-center gap-1.5">
                                  <span>{item.record_identifier}</span>
                                </div>
                              </td>

                              {/* Supplier */}
                              <td className="py-3 px-3 text-slate-700 max-w-[150px] truncate" title={item.vendor_or_counterparty}>
                                {item.vendor_or_counterparty || 'N/A'}
                              </td>

                              {/* Date */}
                              <td className="py-3 px-3 text-slate-600 whitespace-nowrap">
                                {item.transaction_date || 'N/A'}
                              </td>

                              {/* Expected Value */}
                              <td className="py-3 px-3 text-right font-medium text-slate-800 whitespace-nowrap">
                                {item.expected_value || '—'}
                              </td>

                              {/* Actual Value */}
                              <td className="py-3 px-3 text-right font-medium text-slate-800 whitespace-nowrap">
                                {item.actual_value || '—'}
                              </td>

                              {/* Difference */}
                              <td className="py-3 px-3 text-right whitespace-nowrap">
                                {hasDiff ? (
                                  <span
                                    className={`font-bold px-2 py-0.5 rounded text-[11px] border ${
                                      diffNumber > 0
                                        ? 'bg-rose-50 text-rose-800 border-rose-200'
                                        : 'bg-amber-50 text-amber-800 border-amber-200'
                                    }`}
                                  >
                                    {diffNumber > 0 ? `+${diffNumber.toFixed(2)}` : diffNumber.toFixed(2)} {item.currency}
                                  </span>
                                ) : (
                                  <span className="text-slate-400 font-mono text-[11px]">$0.00</span>
                                )}
                              </td>

                              {/* Standardized Match Status */}
                              <td className="py-3 px-3 text-center whitespace-nowrap">
                                <span
                                  className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-[11px] font-semibold border ${statusInfo.badgeClass}`}
                                >
                                  <StatusIcon className="w-3 h-3" />
                                  <span>{statusInfo.label}</span>
                                </span>
                              </td>

                              {/* Audit Reason & Evidence */}
                              <td className="py-3 px-3.5 max-w-xs">
                                <p className="text-slate-800 text-[11px] leading-relaxed line-clamp-2" title={item.evidence_text}>
                                  {item.evidence_text || 'Exact match confirmed.'}
                                </p>
                                {item.action_recommendation && (
                                  <p className="text-slate-500 text-[10px] mt-0.5 italic line-clamp-1" title={item.action_recommendation}>
                                    &rarr; {item.action_recommendation}
                                  </p>
                                )}
                              </td>

                              {/* Actions: Open Record / Review Status */}
                              <td className="py-3 px-3.5 text-right whitespace-nowrap">
                                <div className="flex items-center justify-end gap-1.5">
                                  {/* Button to open invoice if available */}
                                  <button
                                    onClick={() => navigate(`/invoices?search=${encodeURIComponent(item.record_identifier)}`)}
                                    className="p-1 text-slate-400 hover:text-teal-600 transition-colors"
                                    title="View Invoice in Invoice list"
                                  >
                                    <ExternalLink className="w-3.5 h-3.5" />
                                  </button>

                                  <select
                                    value={item.review_status}
                                    onChange={(e) => handleStatusChange(item.id, e.target.value)}
                                    className="text-[11px] font-semibold rounded border py-1 px-2 bg-white border-slate-300 text-slate-700 cursor-pointer"
                                  >
                                    <option value="PENDING">Pending</option>
                                    <option value="CONFIRMED">Confirm Match</option>
                                    <option value="DISMISSED">Dismiss</option>
                                  </select>
                                </div>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
