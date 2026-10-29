import React, { useState, useEffect, useCallback } from 'react';
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
  ChevronRight,
  Building,
  CreditCard,
  Layers,
  ArrowUpDown,
  Lock,
  Copy,
  Info,
  Table,
} from 'lucide-react';
import {
  previewReconciliationFile,
  runLedgerReconciliation,
  runBankReconciliation,
  runCombinedReconciliation,
  getReconciliationBatches,
  getReconciliationBatch,
  updateReconciliationItem,
  confirmBankPayment,
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
      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-100 text-amber-800 border border-amber-300 animate-pulse">
        <AlertTriangle className="w-3 h-3 mr-1 text-amber-600" /> Please confirm
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
        <label className="block text-xs font-medium text-slate-700">
          {label} {required && <span className="text-rose-500 font-bold">*</span>}
        </label>
        <MappingStatusBadge status={status} value={value} />
      </div>
      <select
        value={value || ''}
        onChange={(e) => onChange(fieldKey, e.target.value)}
        className={`w-full text-xs border rounded p-2 bg-white transition-colors focus:ring-teal-500 focus:border-teal-500 ${
          status === 'NEEDS_CONFIRMATION'
            ? 'border-amber-400 bg-amber-50/30 ring-1 ring-amber-300'
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
                  : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-100 hover:border-slate-400'
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

export default function Reconciliation() {
  // Navigation & Mode
  const [activeMode, setActiveMode] = useState('LEDGER'); // 'LEDGER' | 'BANK' | 'COMBINED' | 'HISTORY'
  const [batches, setBatches] = useState([]);
  const [currentBatch, setCurrentBatch] = useState(null);

  // Loading & Message States
  const [isLoading, setIsLoading] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  // Tolerance config (default ±$0.05)
  const [amountTolerance, setAmountTolerance] = useState(0.05);

  // Accounting Ledger State
  const [ledgerFile, setLedgerFile] = useState(null);
  const [ledgerPreview, setLedgerPreview] = useState(null);
  const [ledgerMapping, setLedgerMapping] = useState({});
  const [ledgerMappingStatuses, setLedgerMappingStatuses] = useState({});
  const [ledgerMappingWarnings, setLedgerMappingWarnings] = useState({});
  const [ledgerAmbiguousColumns, setLedgerAmbiguousColumns] = useState({});

  // Bank Statement State
  const [bankFile, setBankFile] = useState(null);
  const [bankPreview, setBankPreview] = useState(null);
  const [bankMapping, setBankMapping] = useState({});
  const [bankMappingStatuses, setBankMappingStatuses] = useState({});
  const [bankMappingWarnings, setBankMappingWarnings] = useState({});
  const [bankAmbiguousColumns, setBankAmbiguousColumns] = useState({});

  // Filtering current batch items
  const [itemSearch, setItemSearch] = useState('');
  const [itemFilter, setItemFilter] = useState('ALL'); // 'ALL' | 'EXACT_MATCH' | 'AMOUNT_MISMATCH' | 'TAX_MISMATCH' | 'MISSING' | 'DUPLICATE' | 'PENDING'

  // Payment Confirmation Modal State
  const [confirmModalItem, setConfirmModalItem] = useState(null);
  const [confirmMethod, setConfirmMethod] = useState('Bank Transfer');
  const [confirmDate, setConfirmDate] = useState('');
  const [confirmNotes, setConfirmNotes] = useState('');
  const [isConfirmingPayment, setIsConfirmingPayment] = useState(false);

  // Fetch past batches on mount (do NOT auto-select batch so upload form is always visible first)
  const loadBatches = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage('');
    try {
      const data = await getReconciliationBatches();
      setBatches(data || []);
    } catch (err) {
      setErrorMessage(err.message || 'Failed to fetch reconciliation history.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadBatches();
  }, [loadBatches]);

  // Handle Ledger File Selection & Preview
  const handleLedgerFileChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLedgerFile(file);
    setErrorMessage('');
    try {
      const prev = await previewReconciliationFile(file, 'LEDGER');
      setLedgerPreview(prev);
      setLedgerMapping(prev.suggested_mapping || {});
      setLedgerMappingStatuses(prev.mapping_statuses || {});
      setLedgerMappingWarnings(prev.mapping_warnings || {});
      setLedgerAmbiguousColumns(prev.ambiguous_columns || {});
    } catch (err) {
      setErrorMessage(`Failed to read ledger file: ${err.message}`);
      setLedgerFile(null);
      setLedgerPreview(null);
      setLedgerMapping({});
      setLedgerMappingStatuses({});
      setLedgerMappingWarnings({});
      setLedgerAmbiguousColumns({});
    }
  };

  // Handle Bank File Selection & Preview
  const handleBankFileChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setBankFile(file);
    setErrorMessage('');
    try {
      const prev = await previewReconciliationFile(file, 'BANK');
      setBankPreview(prev);
      setBankMapping(prev.suggested_mapping || {});
      setBankMappingStatuses(prev.mapping_statuses || {});
      setBankMappingWarnings(prev.mapping_warnings || {});
      setBankAmbiguousColumns(prev.ambiguous_columns || {});
    } catch (err) {
      setErrorMessage(`Failed to read bank file: ${err.message}`);
      setBankFile(null);
      setBankPreview(null);
      setBankMapping({});
      setBankMappingStatuses({});
      setBankMappingWarnings({});
      setBankAmbiguousColumns({});
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

  const handleBankFieldChange = (field, value) => {
    setBankMapping((m) => ({ ...m, [field]: value }));
    setBankMappingStatuses((s) => ({
      ...s,
      [field]: value ? 'USER_SELECTED' : 'UNMAPPED',
    }));
    setBankMappingWarnings((w) => {
      const copy = { ...w };
      delete copy[field];
      return copy;
    });
  };

  // Execute Ledger Reconciliation
  const handleRunLedger = async () => {
    if (!ledgerFile) return;
    setIsProcessing(true);
    setErrorMessage('');
    setSuccessMessage('');
    try {
      const res = await runLedgerReconciliation(ledgerFile, ledgerMapping, amountTolerance);
      setCurrentBatch(res);
      setSuccessMessage(
        `Ledger reconciliation completed successfully: ${res.exact_matches} exact matches, ${res.mismatches} mismatches, ${res.unmatched_records} missing/unmatched.`
      );
      setLedgerFile(null);
      setLedgerPreview(null);
      setLedgerMapping({});
      setLedgerMappingStatuses({});
      setLedgerMappingWarnings({});
      setLedgerAmbiguousColumns({});
      loadBatches();
    } catch (err) {
      setErrorMessage(err.message || 'Failed to run ledger reconciliation.');
    } finally {
      setIsProcessing(false);
    }
  };

  // Execute Bank Reconciliation
  const handleRunBank = async () => {
    if (!bankFile) return;
    setIsProcessing(true);
    setErrorMessage('');
    setSuccessMessage('');
    try {
      const res = await runBankReconciliation(bankFile, bankMapping, amountTolerance);
      setCurrentBatch(res);
      setSuccessMessage(
        `Bank statement reconciliation completed: ${res.exact_matches} cleared payment matches found.`
      );
      setBankFile(null);
      setBankPreview(null);
      setBankMapping({});
      setBankMappingStatuses({});
      setBankMappingWarnings({});
      setBankAmbiguousColumns({});
      loadBatches();
    } catch (err) {
      setErrorMessage(err.message || 'Failed to run bank reconciliation.');
    } finally {
      setIsProcessing(false);
    }
  };

  // Execute Combined Reconciliation
  const handleRunCombined = async () => {
    if (!ledgerFile || !bankFile) {
      setErrorMessage('Both Accounting Ledger and Bank Statement files are required for Combined Reconciliation.');
      return;
    }
    setIsProcessing(true);
    setErrorMessage('');
    setSuccessMessage('');
    try {
      const res = await runCombinedReconciliation(
        ledgerFile,
        bankFile,
        ledgerMapping,
        bankMapping,
        amountTolerance
      );
      setCurrentBatch(res);
      setSuccessMessage(`Combined 4-Way reconciliation completed: ${res.exact_matches} fully verified items.`);
      setLedgerFile(null);
      setLedgerPreview(null);
      setLedgerMapping({});
      setLedgerMappingStatuses({});
      setLedgerMappingWarnings({});
      setLedgerAmbiguousColumns({});
      setBankFile(null);
      setBankPreview(null);
      setBankMapping({});
      setBankMappingStatuses({});
      setBankMappingWarnings({});
      setBankAmbiguousColumns({});
      loadBatches();
    } catch (err) {
      setErrorMessage(err.message || 'Failed to run combined reconciliation.');
    } finally {
      setIsProcessing(false);
    }
  };

  // Switch Batch
  const handleSelectBatch = async (batchId) => {
    setIsLoading(true);
    setErrorMessage('');
    try {
      const res = await getReconciliationBatch(batchId);
      setCurrentBatch(res);
    } catch (err) {
      setErrorMessage(err.message || 'Failed to load batch.');
    } finally {
      setIsLoading(false);
    }
  };

  // Delete Batch
  const handleDeleteBatch = async (batchId, e) => {
    e.stopPropagation();
    if (!window.confirm('Are you sure you want to delete this reconciliation audit record?')) return;
    try {
      await deleteReconciliationBatch(batchId);
      if (currentBatch?.id === batchId) {
        setCurrentBatch(null);
      }
      loadBatches();
      setSuccessMessage('Reconciliation record deleted.');
    } catch (err) {
      setErrorMessage(err.message || 'Failed to delete record.');
    }
  };

  // Update Review Status
  const handleStatusChange = async (itemId, newStatus) => {
    if (!currentBatch) return;
    try {
      const updated = await updateReconciliationItem(currentBatch.id, itemId, { review_status: newStatus });
      setCurrentBatch((prev) => ({
        ...prev,
        items: prev.items.map((it) => (it.id === itemId ? updated : it)),
      }));
    } catch (err) {
      setErrorMessage(err.message || 'Failed to update review status.');
    }
  };

  // Open Confirm Payment Modal
  const openConfirmPaymentModal = (item) => {
    setConfirmModalItem(item);
    setConfirmMethod('Bank Transfer');
    setConfirmDate(item.transaction_date || new Date().toISOString().split('T')[0]);
    setConfirmNotes(`Explicitly reconciled via ${currentBatch?.title || 'Bank Statement'}`);
  };

  // Submit Confirm Payment
  const handleConfirmPaymentSubmit = async (e) => {
    e.preventDefault();
    if (!confirmModalItem || !currentBatch) return;

    setIsConfirmingPayment(true);
    setErrorMessage('');
    try {
      const updatedItem = await confirmBankPayment(currentBatch.id, confirmModalItem.id, {
        payment_method: confirmMethod,
        payment_date: confirmDate || null,
        notes: confirmNotes,
      });

      // Update state
      setCurrentBatch((prev) => ({
        ...prev,
        items: prev.items.map((it) => (it.id === confirmModalItem.id ? updatedItem : it)),
      }));

      setSuccessMessage(
        `Payment of ${confirmModalItem.actual_value} confirmed and successfully posted to accounts payable!`
      );
      setConfirmModalItem(null);
    } catch (err) {
      setErrorMessage(err.message || 'Failed to record payment.');
    } finally {
      setIsConfirmingPayment(false);
    }
  };

  // Export CSV
  const handleExportCsv = async () => {
    if (!currentBatch) return;
    try {
      const filename = `Reconciliation_${currentBatch.batch_type}_Batch_${currentBatch.id}.csv`;
      await downloadReconciliationCsv(currentBatch.id, filename);
    } catch (err) {
      setErrorMessage(err.message || 'Failed to export CSV report.');
    }
  };

  // Filter items in current batch
  const filteredItems = (currentBatch?.items || []).filter((item) => {
    const matchesSearch =
      !itemSearch ||
      item.record_identifier?.toLowerCase().includes(itemSearch.toLowerCase()) ||
      item.vendor_or_counterparty?.toLowerCase().includes(itemSearch.toLowerCase()) ||
      item.evidence_text?.toLowerCase().includes(itemSearch.toLowerCase());

    if (!matchesSearch) return false;

    if (itemFilter === 'EXACT_MATCH') return item.match_status === 'EXACT_MATCH';
    if (itemFilter === 'AMOUNT_MISMATCH') return item.match_status === 'AMOUNT_MISMATCH';
    if (itemFilter === 'TAX_MISMATCH') return item.match_status === 'TAX_MISMATCH';
    if (itemFilter === 'MISSING')
      return (
        item.match_status === 'MISSING_IN_LEDGER' ||
        item.match_status === 'MISSING_IN_INVOICES' ||
        item.match_status === 'UNMATCHED_BANK_TXN'
      );
    if (itemFilter === 'DUPLICATE') return item.match_status === 'DUPLICATE_SUSPECTED';
    if (itemFilter === 'PENDING') return item.review_status === 'PENDING';

    return true;
  });

  return (
    <div className="space-y-6 pb-12">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <Scale className="w-6 h-6 text-teal-600" />
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
              Invoice Verification & Reconciliation Centre
            </h1>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            Audit accounting ledgers, cross-examine bank statement settlements, and perform multi-way financial reconciliation.
          </p>
        </div>

        {/* Global Action Toolbar */}
        <div className="flex items-center space-x-3">
          {currentBatch && (
            <button
              onClick={handleExportCsv}
              className="inline-flex items-center px-3.5 py-2 border border-slate-300 shadow-xs text-sm font-medium rounded-md text-slate-700 bg-white hover:bg-slate-50 transition-colors"
            >
              <Download className="w-4 h-4 mr-2 text-slate-500" />
              Export Audit CSV
            </button>
          )}
          {currentBatch && (
            <button
              onClick={() => {
                setCurrentBatch(null);
                setErrorMessage('');
                setSuccessMessage('');
              }}
              className="inline-flex items-center px-3.5 py-2 border border-transparent shadow-xs text-sm font-medium rounded-md text-white bg-teal-600 hover:bg-teal-700 transition-colors"
            >
              <Upload className="w-4 h-4 mr-2" />
              Upload Another Ledger / Statement
            </button>
          )}
        </div>
      </div>

      {/* Global Alerts */}
      {errorMessage && (
        <div className="p-4 rounded-md bg-rose-50 border border-rose-200 flex items-start space-x-3">
          <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
          <div className="flex-1 text-sm text-rose-800">{errorMessage}</div>
          <button onClick={() => setErrorMessage('')} className="text-rose-500 hover:text-rose-700">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {successMessage && (
        <div className="p-4 rounded-md bg-emerald-50 border border-emerald-200 flex items-start space-x-3">
          <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
          <div className="flex-1 text-sm text-emerald-800">{successMessage}</div>
          <button onClick={() => setSuccessMessage('')} className="text-emerald-500 hover:text-emerald-700">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Mode Navigation Tabs */}
      <div className="border-b border-slate-200">
        <nav className="flex space-x-6 overflow-x-auto">
          <button
            onClick={() => {
              setActiveMode('LEDGER');
              setCurrentBatch(null);
            }}
            className={`py-3 px-1 border-b-2 text-sm font-medium inline-flex items-center space-x-2 transition-colors whitespace-nowrap ${
              activeMode === 'LEDGER' && !currentBatch
                ? 'border-teal-600 text-teal-600'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            <FileSpreadsheet className="w-4 h-4" />
            <span>1. Accounting Ledger</span>
          </button>

          <button
            onClick={() => {
              setActiveMode('BANK');
              setCurrentBatch(null);
            }}
            className={`py-3 px-1 border-b-2 text-sm font-medium inline-flex items-center space-x-2 transition-colors whitespace-nowrap ${
              activeMode === 'BANK' && !currentBatch
                ? 'border-teal-600 text-teal-600'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            <CreditCard className="w-4 h-4" />
            <span>2. Bank Statement</span>
          </button>

          <button
            onClick={() => {
              setActiveMode('COMBINED');
              setCurrentBatch(null);
            }}
            className={`py-3 px-1 border-b-2 text-sm font-medium inline-flex items-center space-x-2 transition-colors whitespace-nowrap ${
              activeMode === 'COMBINED' && !currentBatch
                ? 'border-teal-600 text-teal-600'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            <Layers className="w-4 h-4" />
            <span>3. Combined Reconciliation</span>
          </button>

          <button
            onClick={() => setActiveMode('HISTORY')}
            className={`py-3 px-1 border-b-2 text-sm font-medium inline-flex items-center space-x-2 transition-colors whitespace-nowrap ${
              activeMode === 'HISTORY'
                ? 'border-teal-600 text-teal-600'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            <Clock className="w-4 h-4" />
            <span>Audit History ({batches.length})</span>
          </button>
        </nav>
      </div>

      {/* Main Content Area */}
      {activeMode === 'HISTORY' ? (
        /* History & Batch List */
        <div className="bg-white rounded-lg border border-slate-200 shadow-xs overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-slate-900">Reconciliation Audit Trail & Past Batches</h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Inspect historical reconciliation batches, review match ratios, and download audit CSVs.
              </p>
            </div>
            <button
              onClick={loadBatches}
              className="text-xs text-teal-600 hover:text-teal-800 font-medium inline-flex items-center"
            >
              <RefreshCw className="w-3.5 h-3.5 mr-1" /> Refresh
            </button>
          </div>
          {batches.length === 0 ? (
            <div className="p-8 text-center text-slate-500">
              <Scale className="w-10 h-10 mx-auto text-slate-300 mb-2" />
              <p className="font-medium text-slate-700">No reconciliation records found</p>
              <p className="text-sm text-slate-500 mt-1">
                Upload an Accounting Ledger or Bank Statement above to run an audit.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-slate-200">
              {batches.map((b) => (
                <div
                  key={b.id}
                  onClick={() => handleSelectBatch(b.id)}
                  className={`p-4 sm:px-6 hover:bg-slate-50 cursor-pointer flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 transition-colors ${
                    currentBatch?.id === b.id ? 'bg-teal-50/60 border-l-4 border-teal-600' : ''
                  }`}
                >
                  <div className="space-y-1">
                    <div className="flex items-center space-x-2">
                      <span className="font-medium text-slate-900 text-sm">{b.title}</span>
                      <span
                        className={`px-2 py-0.5 text-xs font-semibold rounded-full ${
                          b.batch_type === 'COMBINED'
                            ? 'bg-purple-100 text-purple-700'
                            : b.batch_type === 'BANK'
                            ? 'bg-blue-100 text-blue-700'
                            : 'bg-emerald-100 text-emerald-700'
                        }`}
                      >
                        {b.batch_type}
                      </span>
                    </div>
                    <div className="text-xs text-slate-500 flex items-center space-x-3">
                      <span>Batch #{b.id}</span>
                      <span>•</span>
                      <span>{new Date(b.created_at).toLocaleString()}</span>
                      <span>•</span>
                      <span>{b.total_records} records processed</span>
                    </div>
                  </div>

                  <div className="flex items-center space-x-6 text-sm">
                    <div className="flex items-center space-x-4 text-xs font-medium">
                      <span className="text-emerald-600">{b.exact_matches} exact</span>
                      <span className="text-amber-600">{b.mismatches} mismatches</span>
                      <span className="text-slate-500">{b.unmatched_records} unmatched</span>
                    </div>

                    <div className="flex items-center space-x-2">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSelectBatch(b.id);
                        }}
                        className="p-1.5 text-slate-400 hover:text-teal-600 rounded transition-colors"
                        title="View batch results"
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                      <button
                        onClick={(e) => handleDeleteBatch(b.id, e)}
                        className="p-1.5 text-slate-400 hover:text-rose-600 rounded transition-colors"
                        title="Delete batch"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : !currentBatch ? (
        /* Upload & Execution Flow for Ledger, Bank, or Combined */
        <div className="space-y-6">
          {/* Matching Tolerance Configuration Bar */}
          <div className="bg-slate-50 rounded-lg p-4 border border-slate-200 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center space-x-3">
              <Sliders className="w-4 h-4 text-slate-500" />
              <div>
                <span className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
                  Reconciliation Matching Tolerance
                </span>
                <p className="text-xs text-slate-500">
                  Allowable rounding difference between records (default ±$0.05).
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-2">
              <label htmlFor="tolerance-input" className="text-xs font-medium text-slate-600">
                Amount Tolerance (±):
              </label>
              <input
                id="tolerance-input"
                type="number"
                step="0.01"
                min="0.00"
                max="5.00"
                value={amountTolerance}
                onChange={(e) => setAmountTolerance(parseFloat(e.target.value) || 0)}
                className="w-24 px-2 py-1 text-xs border border-slate-300 rounded shadow-xs focus:ring-teal-500 focus:border-teal-500 bg-white"
              />
            </div>
          </div>

          {/* ========================================================================= */}
          {/* Mode 1: Accounting Ledger (CSV/XLSX) Option                               */}
          {/* ========================================================================= */}
          {activeMode === 'LEDGER' && (
            <div className="space-y-6">
              {/* Instructions & Required Columns Guide Card */}
              <div className="bg-teal-50/60 border border-teal-200 rounded-lg p-5">
                <div className="flex items-start space-x-3">
                  <Info className="w-5 h-5 text-teal-600 shrink-0 mt-0.5" />
                  <div className="space-y-2 text-xs text-slate-700">
                    <h3 className="font-semibold text-sm text-teal-900">
                      Accounting Ledger Reconciliation Guide
                    </h3>
                    <p>
                      Upload your General Ledger (GL) or Accounts Payable ledger export to verify that every booked transaction
                      matches a corresponding saved invoice in InvoiceIQ.
                    </p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
                      <div className="bg-white p-3 rounded border border-teal-100">
                        <span className="font-semibold text-teal-900 block mb-1">Supported File Formats</span>
                        <ul className="list-disc list-inside space-y-0.5 text-slate-600">
                          <li><strong>CSV (.csv):</strong> Comma, semicolon, or tab delimited (UTF-8, Latin-1).</li>
                          <li><strong>Excel (.xlsx / .xls):</strong> Modern Microsoft Excel workbooks.</li>
                        </ul>
                      </div>
                      <div className="bg-white p-3 rounded border border-teal-100">
                        <span className="font-semibold text-teal-900 block mb-1">Expected Ledger Columns</span>
                        <ul className="list-disc list-inside space-y-0.5 text-slate-600">
                          <li><span className="font-semibold text-rose-600">Invoice Number*</span> (e.g., Invoice Number, Inv No, Doc Number, Bill No)</li>
                          <li><span className="font-semibold text-rose-600">Total Amount*</span> (e.g., Total Amount, Gross, Amount, Total)</li>
                          <li><span>Tax / GST Amount</span> (Optional, e.g., Tax, GST, VAT)</li>
                          <li><span>Vendor / Supplier Name</span> (Optional, e.g., Vendor, Supplier, Payee)</li>
                          <li><span>Posting Date</span> (Optional, e.g., Date, Posting Date)</li>
                        </ul>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Upload Dropzone */}
              <div className="bg-white rounded-lg border border-slate-200 shadow-xs p-6 space-y-6">
                <div>
                  <h2 className="text-base font-semibold text-slate-900">Step 1: Select Accounting Ledger File</h2>
                  <p className="text-xs text-slate-500 mt-1">
                    Choose or drop your accounting ledger spreadsheet below. InvoiceIQ will automatically parse the headers and records.
                  </p>
                </div>

                {!ledgerPreview ? (
                  <div className="border-2 border-dashed border-slate-300 rounded-lg p-8 text-center hover:border-teal-500 transition-colors bg-slate-50/50">
                    <FileSpreadsheet className="w-12 h-12 mx-auto text-slate-400 mb-3" />
                    <label htmlFor="ledger-file-upload" className="cursor-pointer">
                      <span className="text-sm font-semibold text-teal-600 hover:text-teal-700">
                        Click to choose an accounting ledger (.CSV or .XLSX)
                      </span>
                      <span className="text-sm text-slate-500"> or drag and drop</span>
                      <input
                        id="ledger-file-upload"
                        type="file"
                        accept=".csv, .xlsx, .xls"
                        className="hidden"
                        onClick={(e) => {
                          e.target.value = null;
                        }}
                        onChange={handleLedgerFileChange}
                      />
                    </label>
                    <p className="text-xs text-slate-400 mt-2">Maximum file size 10MB • Preserves your existing database</p>
                  </div>
                ) : (
                  <div className="space-y-6">
                    {/* File preview header summary */}
                    <div className="flex items-center justify-between p-3.5 bg-teal-50 border border-teal-200 rounded-md">
                      <div className="flex items-center space-x-3">
                        <FileSpreadsheet className="w-6 h-6 text-teal-600" />
                        <div>
                          <span className="text-sm font-semibold text-slate-900">{ledgerPreview.filename}</span>
                          <div className="text-xs text-teal-800">
                            {ledgerPreview.total_rows} records detected • Format: {ledgerPreview.file_type} • Hash: {ledgerPreview.file_hash?.substring(0, 10)}...
                          </div>
                        </div>
                      </div>
                      <button
                        onClick={() => {
                          setLedgerFile(null);
                          setLedgerPreview(null);
                          setLedgerMapping({});
                          setLedgerMappingStatuses({});
                          setLedgerMappingWarnings({});
                          setLedgerAmbiguousColumns({});
                        }}
                        className="text-xs text-slate-500 hover:text-rose-600 font-medium px-2 py-1 rounded hover:bg-white transition-colors"
                      >
                        Change File
                      </button>
                    </div>

                    {/* Step 2: Column Mapping Step */}
                    <div className="border border-slate-200 rounded-md p-4 bg-slate-50/70 space-y-4">
                      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                        <div>
                          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-700">
                            Step 2: Confirm Column Mapping
                          </h3>
                          <p className="text-xs text-slate-500">
                            Verify or adjust mapped columns before running reconciliation.
                          </p>
                        </div>
                        <div className="flex items-center space-x-2 text-xs">
                          <span className="text-slate-500 font-medium">Statuses:</span>
                          <MappingStatusBadge status="AUTO_MAPPED" />
                          <MappingStatusBadge status="NEEDS_CONFIRMATION" />
                          <MappingStatusBadge status="USER_SELECTED" />
                        </div>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
                        <ColumnMappingField
                          label="Invoice Number"
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
                          label="Total Amount"
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
                          label="Tax / GST Amount"
                          fieldKey="tax_amount"
                          value={ledgerMapping.tax_amount}
                          status={ledgerMappingStatuses.tax_amount}
                          warning={ledgerMappingWarnings.tax_amount}
                          candidates={ledgerAmbiguousColumns.tax_amount}
                          headers={ledgerPreview.headers || []}
                          onChange={handleLedgerFieldChange}
                          onSelectCandidate={handleLedgerFieldChange}
                        />

                        <ColumnMappingField
                          label="Vendor / Payee"
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
                          label="Posting Date"
                          fieldKey="invoice_date"
                          value={ledgerMapping.invoice_date}
                          status={ledgerMappingStatuses.invoice_date}
                          warning={ledgerMappingWarnings.invoice_date}
                          candidates={ledgerAmbiguousColumns.invoice_date}
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
                      </div>
                    </div>

                    {/* Step 3: Preview of Parsed Records */}
                    {ledgerPreview.sample_rows && ledgerPreview.sample_rows.length > 0 && (
                      <div className="border border-slate-200 rounded-md overflow-hidden space-y-2">
                        <div className="px-4 py-2 bg-slate-100 border-b border-slate-200 flex items-center justify-between">
                          <span className="text-xs font-semibold text-slate-700 flex items-center">
                            <Table className="w-3.5 h-3.5 mr-1 text-slate-500" />
                            Step 3: Preview of Parsed Records (First {ledgerPreview.sample_rows.length} rows)
                          </span>
                          <span className="text-[11px] text-slate-500">
                            Verify that columns align correctly before running
                          </span>
                        </div>
                        <div className="overflow-x-auto p-2">
                          <table className="w-full text-left text-xs border-collapse">
                            <thead>
                              <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold text-[11px]">
                                {(ledgerPreview.headers || []).map((h) => (
                                  <th key={h} className="p-2 whitespace-nowrap">
                                    {h}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
                              {ledgerPreview.sample_rows.map((row, rIdx) => (
                                <tr key={rIdx} className="hover:bg-slate-50">
                                  {(ledgerPreview.headers || []).map((h) => (
                                    <td key={h} className="p-2 text-slate-700 whitespace-nowrap">
                                      {row[h] !== undefined && row[h] !== null ? String(row[h]) : '—'}
                                    </td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {/* Step 4: Run Reconciliation Button */}
                    <div className="pt-2">
                      <button
                        onClick={handleRunLedger}
                        disabled={isProcessing || !ledgerMapping.invoice_number || !ledgerMapping.total_amount}
                        className="w-full py-3 px-4 rounded-md text-sm font-semibold text-white bg-teal-600 hover:bg-teal-700 disabled:opacity-50 disabled:cursor-not-allowed shadow-xs transition-colors flex items-center justify-center space-x-2"
                      >
                        {isProcessing ? (
                          <>
                            <RefreshCw className="w-4 h-4 animate-spin" />
                            <span>Comparing Ledger against Saved Invoices...</span>
                          </>
                        ) : (
                          <>
                            <CheckCircle2 className="w-4 h-4" />
                            <span>Run Accounting Ledger Reconciliation</span>
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ========================================================================= */}
          {/* Mode 2: Bank Statement (CSV/XLSX) Option                                  */}
          {/* ========================================================================= */}
          {activeMode === 'BANK' && (
            <div className="space-y-6">
              {/* Instructions Guide Card */}
              <div className="bg-blue-50/60 border border-blue-200 rounded-lg p-5">
                <div className="flex items-start space-x-3">
                  <CreditCard className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
                  <div className="space-y-2 text-xs text-slate-700">
                    <h3 className="font-semibold text-sm text-blue-900">
                      Bank Statement Reconciliation Guide
                    </h3>
                    <p>
                      Upload bank statements to audit cleared debits against recorded invoice payments and detect unrecorded vendor settlements.
                    </p>
                    <div className="p-2.5 bg-amber-50 border border-amber-200 rounded text-amber-900 text-xs flex items-center space-x-2">
                      <Lock className="w-4 h-4 text-amber-700 shrink-0" />
                      <span>
                        <strong>Strict Safety Rule:</strong> Bank imports never automatically mark invoices as paid or alter balances.
                        You must explicitly review and confirm any proposed payment match.
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Upload Dropzone */}
              <div className="bg-white rounded-lg border border-slate-200 shadow-xs p-6 space-y-6">
                <div>
                  <h2 className="text-base font-semibold text-slate-900">Step 1: Select Bank Statement File</h2>
                  <p className="text-xs text-slate-500 mt-1">
                    Upload your bank transaction file (.CSV or .XLSX). Supports withdrawal debits, UTR references, and deposits.
                  </p>
                </div>

                {!bankPreview ? (
                  <div className="border-2 border-dashed border-slate-300 rounded-lg p-8 text-center hover:border-teal-500 transition-colors bg-slate-50/50">
                    <CreditCard className="w-12 h-12 mx-auto text-slate-400 mb-3" />
                    <label htmlFor="bank-file-upload" className="cursor-pointer">
                      <span className="text-sm font-semibold text-teal-600 hover:text-teal-700">
                        Click to choose a bank statement (.CSV or .XLSX)
                      </span>
                      <span className="text-sm text-slate-500"> or drag and drop</span>
                      <input
                        id="bank-file-upload"
                        type="file"
                        accept=".csv, .xlsx, .xls"
                        className="hidden"
                        onClick={(e) => {
                          e.target.value = null;
                        }}
                        onChange={handleBankFileChange}
                      />
                    </label>
                    <p className="text-xs text-slate-400 mt-2">Supports debit/credit columns or signed amount exports</p>
                  </div>
                ) : (
                  <div className="space-y-6">
                    {/* File preview header summary */}
                    <div className="flex items-center justify-between p-3.5 bg-teal-50 border border-teal-200 rounded-md">
                      <div className="flex items-center space-x-3">
                        <CreditCard className="w-6 h-6 text-teal-600" />
                        <div>
                          <span className="text-sm font-semibold text-slate-900">{bankPreview.filename}</span>
                          <div className="text-xs text-teal-800">
                            {bankPreview.total_rows} transactions detected • Format: {bankPreview.file_type}
                          </div>
                        </div>
                      </div>
                      <button
                        onClick={() => {
                          setBankFile(null);
                          setBankPreview(null);
                          setBankMapping({});
                          setBankMappingStatuses({});
                          setBankMappingWarnings({});
                          setBankAmbiguousColumns({});
                        }}
                        className="text-xs text-slate-500 hover:text-rose-600 font-medium px-2 py-1 rounded hover:bg-white transition-colors"
                      >
                        Change File
                      </button>
                    </div>

                    {/* Column Mapping Section */}
                    <div className="border border-slate-200 rounded-md p-4 bg-slate-50/70 space-y-4">
                      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                        <div>
                          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-700">
                            Step 2: Confirm Bank Column Mapping
                          </h3>
                          <p className="text-xs text-slate-500">
                            Select date, narration, debit amount, and UTR/reference columns.
                          </p>
                        </div>
                        <div className="flex items-center space-x-2 text-xs">
                          <span className="text-slate-500 font-medium">Statuses:</span>
                          <MappingStatusBadge status="AUTO_MAPPED" />
                          <MappingStatusBadge status="NEEDS_CONFIRMATION" />
                          <MappingStatusBadge status="USER_SELECTED" />
                        </div>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
                        <ColumnMappingField
                          label="Transaction Date"
                          fieldKey="transaction_date"
                          required
                          value={bankMapping.transaction_date}
                          status={bankMappingStatuses.transaction_date}
                          warning={bankMappingWarnings.transaction_date}
                          candidates={bankAmbiguousColumns.transaction_date}
                          headers={bankPreview.headers || []}
                          onChange={handleBankFieldChange}
                          onSelectCandidate={handleBankFieldChange}
                        />

                        <ColumnMappingField
                          label="Description / Narration"
                          fieldKey="description"
                          required
                          value={bankMapping.description}
                          status={bankMappingStatuses.description}
                          warning={bankMappingWarnings.description}
                          candidates={bankAmbiguousColumns.description}
                          headers={bankPreview.headers || []}
                          onChange={handleBankFieldChange}
                          onSelectCandidate={handleBankFieldChange}
                        />

                        <ColumnMappingField
                          label="Debit (Withdrawal) Amount"
                          fieldKey="debit_amount"
                          value={bankMapping.debit_amount || bankMapping.amount}
                          status={bankMappingStatuses.debit_amount || bankMappingStatuses.amount}
                          warning={bankMappingWarnings.debit_amount || bankMappingWarnings.amount}
                          candidates={bankAmbiguousColumns.debit_amount || bankAmbiguousColumns.amount}
                          headers={bankPreview.headers || []}
                          onChange={handleBankFieldChange}
                          onSelectCandidate={handleBankFieldChange}
                        />

                        <ColumnMappingField
                          label="Credit (Deposit) Amount"
                          fieldKey="credit_amount"
                          value={bankMapping.credit_amount}
                          status={bankMappingStatuses.credit_amount}
                          warning={bankMappingWarnings.credit_amount}
                          candidates={bankAmbiguousColumns.credit_amount}
                          headers={bankPreview.headers || []}
                          onChange={handleBankFieldChange}
                          onSelectCandidate={handleBankFieldChange}
                        />

                        <ColumnMappingField
                          label="Reference / UTR ID"
                          fieldKey="reference_id"
                          value={bankMapping.reference_id}
                          status={bankMappingStatuses.reference_id}
                          warning={bankMappingWarnings.reference_id}
                          candidates={bankAmbiguousColumns.reference_id}
                          headers={bankPreview.headers || []}
                          onChange={handleBankFieldChange}
                          onSelectCandidate={handleBankFieldChange}
                        />
                      </div>
                    </div>

                    {/* Preview of Parsed Bank Records */}
                    {bankPreview.sample_rows && bankPreview.sample_rows.length > 0 && (
                      <div className="border border-slate-200 rounded-md overflow-hidden space-y-2">
                        <div className="px-4 py-2 bg-slate-100 border-b border-slate-200 flex items-center justify-between">
                          <span className="text-xs font-semibold text-slate-700 flex items-center">
                            <Table className="w-3.5 h-3.5 mr-1 text-slate-500" />
                            Step 3: Preview of Bank Statement Records (First {bankPreview.sample_rows.length} transactions)
                          </span>
                        </div>
                        <div className="overflow-x-auto p-2">
                          <table className="w-full text-left text-xs border-collapse">
                            <thead>
                              <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold text-[11px]">
                                {(bankPreview.headers || []).map((h) => (
                                  <th key={h} className="p-2 whitespace-nowrap">
                                    {h}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
                              {bankPreview.sample_rows.map((row, rIdx) => (
                                <tr key={rIdx} className="hover:bg-slate-50">
                                  {(bankPreview.headers || []).map((h) => (
                                    <td key={h} className="p-2 text-slate-700 whitespace-nowrap">
                                      {row[h] !== undefined && row[h] !== null ? String(row[h]) : '—'}
                                    </td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {/* Run Button */}
                    <div className="pt-2">
                      <button
                        onClick={handleRunBank}
                        disabled={isProcessing || !bankMapping.transaction_date || !bankMapping.description}
                        className="w-full py-3 px-4 rounded-md text-sm font-semibold text-white bg-teal-600 hover:bg-teal-700 disabled:opacity-50 disabled:cursor-not-allowed shadow-xs transition-colors flex items-center justify-center space-x-2"
                      >
                        {isProcessing ? (
                          <>
                            <RefreshCw className="w-4 h-4 animate-spin" />
                            <span>Auditing Bank Debits against Invoices & Payments...</span>
                          </>
                        ) : (
                          <>
                            <CreditCard className="w-4 h-4" />
                            <span>Run Bank Statement Reconciliation</span>
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ========================================================================= */}
          {/* Mode 3: Combined 4-Way Reconciliation Option                              */}
          {/* ========================================================================= */}
          {activeMode === 'COMBINED' && (
            <div className="bg-white rounded-lg border border-slate-200 shadow-xs p-6 space-y-6">
              <div>
                <h2 className="text-base font-semibold text-slate-900">Combined 4-Way Financial Reconciliation</h2>
                <p className="text-xs text-slate-500 mt-1">
                  Simultaneously cross-examine all four legs of your financial records:
                  <strong> Invoice record ⟷ General Ledger entry ⟷ Payment record ⟷ Cleared Bank debit</strong>.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Ledger Upload Card */}
                <div className="border border-slate-200 rounded-lg p-4 bg-slate-50/50 space-y-3">
                  <div className="flex items-center space-x-2">
                    <FileSpreadsheet className="w-5 h-5 text-teal-600" />
                    <span className="text-sm font-semibold text-slate-800">1. Accounting Ledger File</span>
                  </div>
                  {!ledgerPreview ? (
                    <input
                      type="file"
                      accept=".csv, .xlsx, .xls"
                      onClick={(e) => {
                        e.target.value = null;
                      }}
                      onChange={handleLedgerFileChange}
                      className="text-xs text-slate-600 file:mr-2 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-xs file:font-semibold file:bg-teal-50 file:text-teal-700 hover:file:bg-teal-100"
                    />
                  ) : (
                    <div className="space-y-3">
                      <div className="text-xs text-emerald-700 font-medium flex items-center justify-between bg-emerald-50 p-2 rounded border border-emerald-200">
                        <span>✓ {ledgerPreview.filename} ({ledgerPreview.total_rows} rows)</span>
                        <button
                          onClick={() => {
                            setLedgerFile(null);
                            setLedgerPreview(null);
                            setLedgerMapping({});
                            setLedgerMappingStatuses({});
                            setLedgerMappingWarnings({});
                            setLedgerAmbiguousColumns({});
                          }}
                          className="text-slate-500 hover:text-rose-600 text-xs font-semibold"
                        >
                          Change
                        </button>
                      </div>

                      {/* Ledger Column Mapping in Combined Mode */}
                      <div className="bg-white p-3 rounded border border-slate-200 space-y-3 text-xs">
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-slate-700 block">Ledger Column Mapping:</span>
                          <span className="text-[10px] text-slate-500">Auto-mapped</span>
                        </div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                          <ColumnMappingField
                            label="Invoice #"
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
                            label="Total Amount"
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
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Bank Upload Card */}
                <div className="border border-slate-200 rounded-lg p-4 bg-slate-50/50 space-y-3">
                  <div className="flex items-center space-x-2">
                    <CreditCard className="w-5 h-5 text-teal-600" />
                    <span className="text-sm font-semibold text-slate-800">2. Bank Statement File</span>
                  </div>
                  {!bankPreview ? (
                    <input
                      type="file"
                      accept=".csv, .xlsx, .xls"
                      onClick={(e) => {
                        e.target.value = null;
                      }}
                      onChange={handleBankFileChange}
                      className="text-xs text-slate-600 file:mr-2 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-xs file:font-semibold file:bg-teal-50 file:text-teal-700 hover:file:bg-teal-100"
                    />
                  ) : (
                    <div className="space-y-3">
                      <div className="text-xs text-emerald-700 font-medium flex items-center justify-between bg-emerald-50 p-2 rounded border border-emerald-200">
                        <span>✓ {bankPreview.filename} ({bankPreview.total_rows} txns)</span>
                        <button
                          onClick={() => {
                            setBankFile(null);
                            setBankPreview(null);
                            setBankMapping({});
                            setBankMappingStatuses({});
                            setBankMappingWarnings({});
                            setBankAmbiguousColumns({});
                          }}
                          className="text-slate-500 hover:text-rose-600 text-xs font-semibold"
                        >
                          Change
                        </button>
                      </div>

                      {/* Bank Column Mapping in Combined Mode */}
                      <div className="bg-white p-3 rounded border border-slate-200 space-y-3 text-xs">
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-slate-700 block">Bank Column Mapping:</span>
                          <span className="text-[10px] text-slate-500">Auto-mapped</span>
                        </div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                          <ColumnMappingField
                            label="Transaction Date"
                            fieldKey="transaction_date"
                            required
                            value={bankMapping.transaction_date}
                            status={bankMappingStatuses.transaction_date}
                            warning={bankMappingWarnings.transaction_date}
                            candidates={bankAmbiguousColumns.transaction_date}
                            headers={bankPreview.headers || []}
                            onChange={handleBankFieldChange}
                            onSelectCandidate={handleBankFieldChange}
                          />
                          <ColumnMappingField
                            label="Debit Amount"
                            fieldKey="debit_amount"
                            required
                            value={bankMapping.debit_amount || bankMapping.amount}
                            status={bankMappingStatuses.debit_amount || bankMappingStatuses.amount}
                            warning={bankMappingWarnings.debit_amount || bankMappingWarnings.amount}
                            candidates={bankAmbiguousColumns.debit_amount || bankAmbiguousColumns.amount}
                            headers={bankPreview.headers || []}
                            onChange={handleBankFieldChange}
                            onSelectCandidate={handleBankFieldChange}
                          />
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Combined Previews */}
              {ledgerPreview && bankPreview && (
                <div className="p-3 bg-purple-50 border border-purple-200 rounded text-xs text-purple-900 flex items-center space-x-2">
                  <Check className="w-4 h-4 text-purple-700 shrink-0" />
                  <span>
                    Ready for 4-way cross-examination: <strong>{ledgerPreview.total_rows}</strong> ledger entries and{' '}
                    <strong>{bankPreview.total_rows}</strong> bank transactions will be audited against your saved invoices and payments.
                  </span>
                </div>
              )}

              {/* Combined Run Button */}
              <button
                onClick={handleRunCombined}
                disabled={isProcessing || !ledgerPreview || !bankPreview}
                className="w-full py-3 px-4 rounded-md text-sm font-semibold text-white bg-purple-600 hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed shadow-xs transition-colors flex items-center justify-center space-x-2"
              >
                {isProcessing ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Executing 4-Way Cross-Verification...</span>
                  </>
                ) : (
                  <>
                    <Layers className="w-4 h-4" />
                    <span>Run Combined 4-Way Reconciliation</span>
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      ) : null}

      {/* ========================================================================= */}
      {/* Discrepancy & Batch Detail View (Rendered when a batch is active)          */}
      {/* ========================================================================= */}
      {currentBatch && (
        <div className="space-y-6 animate-in fade-in duration-200">
          {/* Auditor Verification Required Notice */}
          <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg flex items-start space-x-3 text-xs text-amber-900">
            <ShieldCheck className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <strong className="font-semibold block text-sm text-amber-950 mb-0.5">
                Auditor Review Required Before Financial Changes
              </strong>
              These reconciliation results highlight exact matches, amount discrepancies, tax differences, and missing entries.
              Financial balances and records are protected and <strong>never altered automatically</strong>.
              Review each item and update status as confirmed, investigating, or dismissed.
            </div>
          </div>

          {/* Summary Stat Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-xs">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Total Records</span>
              <div className="text-2xl font-bold text-slate-900 mt-1">{currentBatch.total_records}</div>
              <div className="text-xs text-slate-400 mt-1 truncate">
                {currentBatch.ledger_filename || currentBatch.bank_filename || 'Audit Run'}
              </div>
            </div>

            <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-xs">
              <span className="text-xs font-semibold text-emerald-600 uppercase tracking-wider flex items-center">
                <CheckCircle2 className="w-3.5 h-3.5 mr-1" /> Exact Matches
              </span>
              <div className="text-2xl font-bold text-emerald-700 mt-1">{currentBatch.exact_matches}</div>
              <div className="text-xs text-slate-400 mt-1">Verified within tolerance</div>
            </div>

            <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-xs">
              <span className="text-xs font-semibold text-amber-600 uppercase tracking-wider flex items-center">
                <AlertTriangle className="w-3.5 h-3.5 mr-1" /> Mismatches
              </span>
              <div className="text-2xl font-bold text-amber-700 mt-1">{currentBatch.mismatches}</div>
              <div className="text-xs text-slate-400 mt-1">Amount / Tax / Duplicates</div>
            </div>

            <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-xs">
              <span className="text-xs font-semibold text-rose-600 uppercase tracking-wider flex items-center">
                <HelpCircle className="w-3.5 h-3.5 mr-1" /> Missing / Unmatched
              </span>
              <div className="text-2xl font-bold text-rose-700 mt-1">{currentBatch.unmatched_records}</div>
              <div className="text-xs text-slate-400 mt-1">Missing in Ledger or Invoices</div>
            </div>
          </div>

          {/* Discrepancy Table Card */}
          <div className="bg-white rounded-lg border border-slate-200 shadow-xs overflow-hidden">
            {/* Table Header & Filter Bar */}
            <div className="px-6 py-4 border-b border-slate-200 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
              <div>
                <h3 className="text-base font-semibold text-slate-900">{currentBatch.title}</h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Processed on {new Date(currentBatch.created_at).toLocaleString()} • Batch #{currentBatch.id} • Tolerance: ±${currentBatch.amount_tolerance}
                </p>
              </div>

              {/* Filter Tabs & Search */}
              <div className="flex flex-col sm:flex-row sm:items-center gap-3">
                <div className="relative">
                  <Search className="w-4 h-4 text-slate-400 absolute left-2.5 top-2.5" />
                  <input
                    type="text"
                    placeholder="Search by invoice # or vendor..."
                    value={itemSearch}
                    onChange={(e) => setItemSearch(e.target.value)}
                    className="pl-8 pr-3 py-1.5 text-xs border border-slate-300 rounded shadow-xs focus:ring-teal-500 focus:border-teal-500 w-56"
                  />
                </div>

                <div className="flex items-center space-x-1 border border-slate-200 rounded p-1 bg-slate-50 text-xs overflow-x-auto">
                  <button
                    onClick={() => setItemFilter('ALL')}
                    className={`px-2 py-1 rounded font-medium whitespace-nowrap ${
                      itemFilter === 'ALL' ? 'bg-white shadow-xs text-slate-900' : 'text-slate-600'
                    }`}
                  >
                    All ({currentBatch.items.length})
                  </button>
                  <button
                    onClick={() => setItemFilter('EXACT_MATCH')}
                    className={`px-2 py-1 rounded font-medium whitespace-nowrap ${
                      itemFilter === 'EXACT_MATCH' ? 'bg-white shadow-xs text-emerald-700' : 'text-slate-600'
                    }`}
                  >
                    Exact ({currentBatch.items.filter((i) => i.match_status === 'EXACT_MATCH').length})
                  </button>
                  <button
                    onClick={() => setItemFilter('AMOUNT_MISMATCH')}
                    className={`px-2 py-1 rounded font-medium whitespace-nowrap ${
                      itemFilter === 'AMOUNT_MISMATCH' ? 'bg-white shadow-xs text-amber-700' : 'text-slate-600'
                    }`}
                  >
                    Amount Diff ({currentBatch.items.filter((i) => i.match_status === 'AMOUNT_MISMATCH').length})
                  </button>
                  <button
                    onClick={() => setItemFilter('MISSING')}
                    className={`px-2 py-1 rounded font-medium whitespace-nowrap ${
                      itemFilter === 'MISSING' ? 'bg-white shadow-xs text-rose-700' : 'text-slate-600'
                    }`}
                  >
                    Missing ({currentBatch.items.filter((i) => i.match_status.includes('MISSING') || i.match_status.includes('UNMATCHED')).length})
                  </button>
                  <button
                    onClick={() => setItemFilter('DUPLICATE')}
                    className={`px-2 py-1 rounded font-medium whitespace-nowrap ${
                      itemFilter === 'DUPLICATE' ? 'bg-white shadow-xs text-purple-700' : 'text-slate-600'
                    }`}
                  >
                    Duplicates ({currentBatch.items.filter((i) => i.match_status === 'DUPLICATE_SUSPECTED').length})
                  </button>
                </div>
              </div>
            </div>

            {/* Items Discrepancy Table */}
            {filteredItems.length === 0 ? (
              <div className="p-8 text-center text-slate-500">
                <p className="text-sm font-medium">No records match the selected filter.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-slate-50/80 border-b border-slate-200 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                      <th className="py-3 px-4">Record Identifier</th>
                      <th className="py-3 px-4">Vendor / Payee</th>
                      <th className="py-3 px-4">Date</th>
                      <th className="py-3 px-4">Expected Value (InvoiceIQ)</th>
                      <th className="py-3 px-4">Actual Value (Ledger/Bank)</th>
                      <th className="py-3 px-4">Difference</th>
                      <th className="py-3 px-4">Match Status</th>
                      <th className="py-3 px-4">Audit Evidence & Action</th>
                      <th className="py-3 px-4 text-right">Review Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 text-xs text-slate-700">
                    {filteredItems.map((item) => {
                      const isBankPendingPayment =
                        item.item_type === 'BANK' &&
                        item.review_status === 'PENDING' &&
                        item.match_status === 'AMBIGUOUS_MATCH' &&
                        item.invoice_id;

                      const diffNumber = item.discrepancy_amount ? parseFloat(item.discrepancy_amount) : 0;
                      const hasDiscrepancy = Math.abs(diffNumber) > 0.001;

                      return (
                        <tr key={item.id} className="hover:bg-slate-50/60 transition-colors">
                          {/* Record ID & Type */}
                          <td className="py-3 px-4 font-mono font-medium text-slate-900 whitespace-nowrap">
                            <div className="flex items-center space-x-1.5">
                              <span
                                className={`px-1.5 py-0.5 text-[10px] rounded font-sans uppercase font-bold ${
                                  item.item_type === 'LEDGER'
                                    ? 'bg-blue-50 text-blue-700 border border-blue-200'
                                    : item.item_type === 'BANK'
                                    ? 'bg-amber-50 text-amber-700 border border-amber-200'
                                    : 'bg-purple-50 text-purple-700 border border-purple-200'
                                }`}
                              >
                                {item.item_type}
                              </span>
                              <span>{item.record_identifier}</span>
                            </div>
                          </td>

                          {/* Vendor */}
                          <td className="py-3 px-4 font-medium text-slate-800 whitespace-nowrap">
                            {item.vendor_or_counterparty || 'N/A'}
                          </td>

                          {/* Date */}
                          <td className="py-3 px-4 text-slate-500 whitespace-nowrap">
                            {item.transaction_date || 'N/A'}
                          </td>

                          {/* Expected Value */}
                          <td className="py-3 px-4 font-medium text-slate-900 whitespace-nowrap">
                            {item.expected_value || 'N/A'}
                          </td>

                          {/* Actual Value */}
                          <td className="py-3 px-4 font-medium text-slate-900 whitespace-nowrap">
                            {item.actual_value || 'N/A'}
                          </td>

                          {/* Difference */}
                          <td className="py-3 px-4 whitespace-nowrap">
                            {hasDiscrepancy ? (
                              <span
                                className={`font-semibold px-2 py-0.5 rounded text-[11px] ${
                                  diffNumber > 0
                                    ? 'bg-rose-50 text-rose-700 border border-rose-200'
                                    : 'bg-amber-50 text-amber-700 border border-amber-200'
                                }`}
                              >
                                {diffNumber > 0 ? `+${diffNumber.toFixed(2)}` : diffNumber.toFixed(2)} {item.currency}
                              </span>
                            ) : (
                              <span className="text-slate-400 font-mono text-[11px]">$0.00</span>
                            )}
                          </td>

                          {/* Match Status Badge */}
                          <td className="py-3 px-4 whitespace-nowrap">
                            {item.match_status === 'EXACT_MATCH' && (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-100 text-emerald-800">
                                <CheckCircle2 className="w-3 h-3 mr-1" /> Exact Match
                              </span>
                            )}
                            {item.match_status === 'AMOUNT_MISMATCH' && (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-100 text-amber-800">
                                <AlertTriangle className="w-3 h-3 mr-1" /> Amount Mismatch
                              </span>
                            )}
                            {item.match_status === 'TAX_MISMATCH' && (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-orange-100 text-orange-800">
                                <AlertTriangle className="w-3 h-3 mr-1" /> Tax Mismatch
                              </span>
                            )}
                            {item.match_status === 'MISSING_IN_LEDGER' && (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-purple-100 text-purple-800">
                                <AlertCircle className="w-3 h-3 mr-1" /> Missing in Ledger
                              </span>
                            )}
                            {item.match_status === 'MISSING_IN_INVOICES' && (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-rose-100 text-rose-800">
                                <AlertCircle className="w-3 h-3 mr-1" /> Missing in Invoices
                              </span>
                            )}
                            {item.match_status === 'DUPLICATE_SUSPECTED' && (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-rose-100 text-rose-800">
                                <Copy className="w-3 h-3 mr-1" /> Duplicate Suspected
                              </span>
                            )}
                            {item.match_status === 'UNMATCHED_BANK_TXN' && (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-slate-100 text-slate-700">
                                Unmatched Bank Txn
                              </span>
                            )}
                            {item.match_status === 'AMBIGUOUS_MATCH' && (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-indigo-100 text-indigo-800">
                                Unrecorded Settlement
                              </span>
                            )}
                          </td>

                          {/* Evidence & Action */}
                          <td className="py-3 px-4 max-w-xs">
                            <p className="text-slate-800 text-[11px] leading-relaxed line-clamp-2" title={item.evidence_text}>
                              {item.evidence_text}
                            </p>
                            <p className="text-slate-500 text-[10px] mt-0.5 italic line-clamp-1" title={item.action_recommendation}>
                              → {item.action_recommendation}
                            </p>
                          </td>

                          {/* Actions / Review Status */}
                          <td className="py-3 px-4 text-right whitespace-nowrap">
                            <div className="flex flex-col items-end space-y-1.5">
                              {isBankPendingPayment ? (
                                <button
                                  onClick={() => openConfirmPaymentModal(item)}
                                  className="inline-flex items-center px-2.5 py-1 text-xs font-semibold rounded bg-teal-600 hover:bg-teal-700 text-white shadow-xs transition-colors"
                                >
                                  <Check className="w-3.5 h-3.5 mr-1" /> Record Payment
                                </button>
                              ) : (
                                <select
                                  value={item.review_status}
                                  onChange={(e) => handleStatusChange(item.id, e.target.value)}
                                  className={`text-[11px] font-medium rounded border py-1 px-2 ${
                                    item.review_status === 'CONFIRMED'
                                      ? 'border-emerald-300 bg-emerald-50 text-emerald-800'
                                      : item.review_status === 'INVESTIGATING'
                                      ? 'border-amber-300 bg-amber-50 text-amber-800'
                                      : item.review_status === 'DISMISSED'
                                      ? 'border-slate-300 bg-slate-50 text-slate-600'
                                      : 'border-blue-300 bg-blue-50 text-blue-800'
                                  }`}
                                >
                                  <option value="PENDING">PENDING</option>
                                  <option value="CONFIRMED">CONFIRMED</option>
                                  <option value="INVESTIGATING">INVESTIGATING</option>
                                  <option value="DISMISSED">DISMISSED</option>
                                </select>
                              )}
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

      {/* Explicit Payment Confirmation Modal */}
      {confirmModalItem && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-lg max-w-lg w-full shadow-xl border border-slate-200 overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div className="flex items-center space-x-2">
                <ShieldCheck className="w-5 h-5 text-teal-600" />
                <h3 className="text-base font-semibold text-slate-900">Confirm & Record Bank Payment</h3>
              </div>
              <button
                onClick={() => setConfirmModalItem(null)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body Form */}
            <form onSubmit={handleConfirmPaymentSubmit} className="p-6 space-y-4">
              {/* Critical Safety Notice */}
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-md text-xs text-amber-800 leading-relaxed flex items-start space-x-2">
                <Lock className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                <div>
                  <strong>Financial Safety Enforcement:</strong> Bank statement imports never automatically alter balances.
                  Confirming this action will permanently record an official payment of{' '}
                  <span className="font-bold underline">{confirmModalItem.actual_value}</span> against{' '}
                  <span className="font-bold">{confirmModalItem.vendor_or_counterparty}</span>.
                </div>
              </div>

              {/* Form Fields */}
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  Payment Amount
                </label>
                <input
                  type="text"
                  readOnly
                  value={confirmModalItem.actual_value}
                  className="w-full text-sm font-semibold bg-slate-100 border border-slate-300 rounded px-3 py-2 text-slate-800"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Payment Date <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="date"
                    required
                    value={confirmDate}
                    onChange={(e) => setConfirmDate(e.target.value)}
                    className="w-full text-xs border border-slate-300 rounded px-2.5 py-1.5 focus:ring-teal-500 focus:border-teal-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Payment Method <span className="text-rose-500">*</span>
                  </label>
                  <select
                    value={confirmMethod}
                    onChange={(e) => setConfirmMethod(e.target.value)}
                    className="w-full text-xs border border-slate-300 rounded px-2.5 py-1.5 focus:ring-teal-500 focus:border-teal-500 bg-white"
                  >
                    <option value="Bank Transfer">Bank Transfer</option>
                    <option value="Wire Transfer">Wire Transfer</option>
                    <option value="NEFT/RTGS">NEFT / RTGS</option>
                    <option value="Direct Debit">Direct Debit</option>
                    <option value="Credit Card">Credit Card</option>
                    <option value="Cheque">Cheque</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  Bank Reference / UTR
                </label>
                <input
                  type="text"
                  readOnly
                  value={confirmModalItem.record_identifier}
                  className="w-full text-xs bg-slate-100 border border-slate-300 rounded px-2.5 py-1.5 text-slate-600 font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Audit Notes</label>
                <textarea
                  rows={2}
                  value={confirmNotes}
                  onChange={(e) => setConfirmNotes(e.target.value)}
                  className="w-full text-xs border border-slate-300 rounded px-2.5 py-1.5 focus:ring-teal-500 focus:border-teal-500"
                  placeholder="Optional audit justification..."
                />
              </div>

              {/* Modal Footer Actions */}
              <div className="pt-3 border-t border-slate-200 flex items-center justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => setConfirmModalItem(null)}
                  className="px-3.5 py-2 text-xs font-medium text-slate-700 bg-white border border-slate-300 rounded hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isConfirmingPayment}
                  className="inline-flex items-center px-4 py-2 text-xs font-semibold rounded text-white bg-teal-600 hover:bg-teal-700 shadow-xs disabled:opacity-50"
                >
                  {isConfirmingPayment ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" /> Recording Payment...
                    </>
                  ) : (
                    <>
                      <Check className="w-3.5 h-3.5 mr-1.5" /> Confirm & Post Payment
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
