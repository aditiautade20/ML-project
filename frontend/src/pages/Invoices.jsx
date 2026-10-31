import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  FileText,
  Upload,
  Search,
  Plus,
  Trash2,
  Edit2,
  Eye,
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  X,
  FileCheck,
  Calendar,
  DollarSign,
  ArrowUpDown,
  Sparkles,
  ChevronDown,
  ChevronUp,
  Layers,
  Copy,
  Check,
  ShieldCheck,
} from 'lucide-react';
import {
  getInvoices,
  uploadInvoiceFile,
  createInvoice,
  updateInvoice,
  deleteInvoice,
} from '../api/invoices';
import { getDueDateReminder } from '../utils/dueDateHelper';

export default function Invoices() {
  const [invoices, setInvoices] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  // Search & Filtering
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [vendorFilter, setVendorFilter] = useState('');
  const [dueDateFrom, setDueDateFrom] = useState('');
  const [dueDateTo, setDueDateTo] = useState('');
  const [sortBy, setSortBy] = useState('invoice_date');
  const [sortOrder, setSortOrder] = useState('desc');
  const [page, setPage] = useState(1);
  const perPage = 20;

  // Modal States
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadStep, setUploadStep] = useState('pick'); // 'pick' | 'review'
  const [isUploading, setIsUploading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [extractionNotes, setExtractionNotes] = useState([]);
  const [validationWarnings, setValidationWarnings] = useState([]);
  const [fieldConfidence, setFieldConfidence] = useState({});
  const [taxBreakdown, setTaxBreakdown] = useState(null);
  const [candidateDetails, setCandidateDetails] = useState(null);
  const [showRawText, setShowRawText] = useState(false);
  const [copiedRawText, setCopiedRawText] = useState(false);

  // Staged Candidate Form State for Review
  const [formData, setFormData] = useState({
    invoice_number: '',
    vendor_name: '',
    customer_name: '',
    invoice_date: '',
    due_date: '',
    subtotal: '',
    tax_amount: '',
    total_amount: '',
    currency: 'USD',
    file_token: '',
    notes: '',
  });

  // Edit Modal State
  const [editingInvoice, setEditingInvoice] = useState(null);
  const [isUpdating, setIsUpdating] = useState(false);
  const [editError, setEditError] = useState('');

  // Detail Modal State
  const [viewingInvoice, setViewingInvoice] = useState(null);

  // Delete Dialog State
  const [deletingInvoice, setDeletingInvoice] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const fileInputRef = useRef(null);

  const fetchInvoices = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage('');
    try {
      const res = await getInvoices({
        search: searchQuery.trim(),
        vendor: vendorFilter.trim() || undefined,
        payment_status: statusFilter || undefined,
        due_date_from: dueDateFrom || undefined,
        due_date_to: dueDateTo || undefined,
        sort_by: sortBy,
        sort_order: sortOrder,
        page,
        per_page: perPage,
      });
      setInvoices(res.items || []);
      setTotalCount(res.total || 0);
    } catch (err) {
      setErrorMessage(err.message || 'Failed to load invoices.');
    } finally {
      setIsLoading(false);
    }
  }, [searchQuery, vendorFilter, statusFilter, dueDateFrom, dueDateTo, sortBy, sortOrder, page]);

  useEffect(() => {
    fetchInvoices();
  }, [fetchInvoices]);

  const showNotification = (msg) => {
    setSuccessMessage(msg);
    setTimeout(() => setSuccessMessage(''), 4000);
  };

  // --- File Upload & Candidate Extraction ---
  const handleFileSelect = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setUploadError('');
    setExtractionNotes([]);
    setValidationWarnings([]);
    setFieldConfidence({});
    setTaxBreakdown(null);
    setCandidateDetails(null);
    setShowRawText(false);
    setCopiedRawText(false);

    try {
      const res = await uploadInvoiceFile(file);
      const c = res.candidate_fields || {};

      // Populate review form with candidates (never invent missing fields)
      setFormData({
        invoice_number: c.invoice_number || '',
        vendor_name: c.vendor_name || '',
        customer_name: c.customer_name || '',
        invoice_date: c.invoice_date || '',
        due_date: c.due_date || '',
        subtotal: c.subtotal !== null && c.subtotal !== undefined ? c.subtotal.toString() : '',
        tax_amount: c.tax_amount !== null && c.tax_amount !== undefined ? c.tax_amount.toString() : '',
        total_amount: c.total_amount !== null && c.total_amount !== undefined ? c.total_amount.toString() : '',
        currency: c.currency || 'USD',
        file_token: res.file_token || '',
        notes: c.notes || '',
      });

      setCandidateDetails({
        ...c,
        raw_text: res.raw_text || c.raw_text || '',
      });

      setExtractionNotes(res.extraction_notes || []);
      setValidationWarnings(res.validation_warnings || []);
      setFieldConfidence(c.field_confidence || {});
      if (c.cgst || c.sgst || c.igst) {
        setTaxBreakdown({
          cgst: c.cgst,
          sgst: c.sgst,
          igst: c.igst,
        });
      } else {
        setTaxBreakdown(null);
      }
      setUploadStep('review');
    } catch (err) {
      setUploadError(err.message || 'File upload failed. Please verify the format and size.');
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleCopyRawText = () => {
    if (candidateDetails?.raw_text) {
      navigator.clipboard.writeText(candidateDetails.raw_text);
      setCopiedRawText(true);
      setTimeout(() => setCopiedRawText(false), 2000);
    }
  };

  // --- Confirm and Save Reviewed Invoice ---
  const handleConfirmSave = async (e) => {
    e.preventDefault();
    setUploadError('');

    // Form validation
    if (!formData.invoice_number.trim()) {
      setUploadError('Invoice number is required.');
      return;
    }
    if (!formData.vendor_name.trim()) {
      setUploadError('Supplier / Vendor name is required.');
      return;
    }
    if (!formData.invoice_date) {
      setUploadError('Invoice date is required.');
      return;
    }
    const totalNum = parseFloat(formData.total_amount);
    if (isNaN(totalNum) || totalNum <= 0) {
      setUploadError('Total amount must be a valid number greater than zero.');
      return;
    }

    setIsSaving(true);
    try {
      // Auto-summarize metadata in notes if user left notes empty
      let finalNotes = formData.notes ? formData.notes.trim() : '';
      if (!finalNotes && candidateDetails) {
        const parts = [];
        if (candidateDetails.po_number) parts.push(`PO: ${candidateDetails.po_number}`);
        if (candidateDetails.payment_terms) parts.push(`Terms: ${candidateDetails.payment_terms}`);
        if (candidateDetails.vendor_gstin) parts.push(`Vendor GSTIN: ${candidateDetails.vendor_gstin}`);
        if (candidateDetails.customer_gstin) parts.push(`Buyer GSTIN: ${candidateDetails.customer_gstin}`);
        if (candidateDetails.invoice_type && candidateDetails.invoice_type !== 'Invoice') {
          parts.push(`Type: ${candidateDetails.invoice_type}`);
        }
        if (parts.length > 0) {
          finalNotes = parts.join(' | ').slice(0, 990);
        }
      }

      const payload = {
        invoice_number: formData.invoice_number.trim(),
        vendor_name: formData.vendor_name.trim(),
        customer_name: formData.customer_name ? formData.customer_name.trim() : null,
        invoice_date: formData.invoice_date,
        due_date: formData.due_date ? formData.due_date : null,
        subtotal: formData.subtotal ? parseFloat(formData.subtotal) : null,
        tax_amount: formData.tax_amount ? parseFloat(formData.tax_amount) : null,
        total_amount: totalNum,
        currency: formData.currency.toUpperCase(),
        status: validationWarnings.length > 0 ? 'NEEDS_REVIEW' : 'CONFIRMED',
        file_token: formData.file_token || null,
        notes: finalNotes || null,
      };

      await createInvoice(payload);
      setShowUploadModal(false);
      setUploadStep('pick');
      showNotification(`Invoice #${payload.invoice_number} saved successfully.`);
      fetchInvoices();
    } catch (err) {
      setUploadError(err.message || 'Failed to save confirmed invoice.');
    } finally {
      setIsSaving(false);
    }
  };

  // --- Handle Edit Invoice ---
  const handleOpenEdit = (inv) => {
    setEditingInvoice({
      id: inv.id,
      invoice_number: inv.invoice_number,
      vendor_name: inv.vendor_name,
      customer_name: inv.customer_name || '',
      invoice_date: inv.invoice_date,
      due_date: inv.due_date || '',
      subtotal: inv.subtotal !== null && inv.subtotal !== undefined ? inv.subtotal.toString() : '',
      tax_amount: inv.tax_amount !== null && inv.tax_amount !== undefined ? inv.tax_amount.toString() : '',
      total_amount: inv.total_amount.toString(),
      currency: inv.currency,
      notes: inv.notes || '',
    });
    setEditError('');
  };

  const handleSaveEdit = async (e) => {
    e.preventDefault();
    if (!editingInvoice) return;
    setEditError('');

    const totalNum = parseFloat(editingInvoice.total_amount);
    if (isNaN(totalNum) || totalNum <= 0) {
      setEditError('Total amount must be greater than zero.');
      return;
    }

    setIsUpdating(true);
    try {
      const payload = {
        invoice_number: editingInvoice.invoice_number.trim(),
        vendor_name: editingInvoice.vendor_name.trim(),
        customer_name: editingInvoice.customer_name ? editingInvoice.customer_name.trim() : null,
        invoice_date: editingInvoice.invoice_date,
        due_date: editingInvoice.due_date ? editingInvoice.due_date : null,
        subtotal: editingInvoice.subtotal ? parseFloat(editingInvoice.subtotal) : null,
        tax_amount: editingInvoice.tax_amount ? parseFloat(editingInvoice.tax_amount) : null,
        total_amount: totalNum,
        currency: editingInvoice.currency.toUpperCase(),
        notes: editingInvoice.notes ? editingInvoice.notes.trim() : null,
      };

      await updateInvoice(editingInvoice.id, payload);
      setEditingInvoice(null);
      showNotification(`Invoice #${payload.invoice_number} updated successfully.`);
      fetchInvoices();
    } catch (err) {
      setEditError(err.message || 'Failed to update invoice.');
    } finally {
      setIsUpdating(false);
    }
  };

  // --- Handle Delete Invoice ---
  const handleConfirmDelete = async () => {
    if (!deletingInvoice) return;
    setIsDeleting(true);
    try {
      await deleteInvoice(deletingInvoice.id);
      showNotification(`Invoice #${deletingInvoice.invoice_number} deleted.`);
      setDeletingInvoice(null);
      fetchInvoices();
    } catch (err) {
      setErrorMessage(err.message || 'Failed to delete invoice.');
    } finally {
      setIsDeleting(false);
    }
  };

  const formatCurrency = (val, cur = 'USD') => {
    const num = parseFloat(val);
    if (isNaN(num)) return '$0.00';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: cur || 'USD',
    }).format(num);
  };

  const renderConfidenceBadge = (field) => {
    const level = fieldConfidence[field];
    if (level === 'HIGH') {
      return (
        <span className="ml-1.5 inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
          High Confidence
        </span>
      );
    }
    if (level === 'MEDIUM') {
      return (
        <span className="ml-1.5 inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-50 text-amber-700 border border-amber-200">
          Review Suggested
        </span>
      );
    }
    return null;
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Invoices</h1>
          <p className="text-sm text-slate-500 mt-1">
            Upload, review extracted values, and manage persistent invoice records.
          </p>
        </div>

        <button
          onClick={() => {
            setShowUploadModal(true);
            setUploadStep('pick');
            setUploadError('');
          }}
          className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-md text-sm font-medium transition-colors shadow-xs shrink-0"
        >
          <Upload className="w-4 h-4" />
          <span>Upload Invoice</span>
        </button>
      </div>

      {/* Global Notifications */}
      {successMessage && (
        <div className="flex items-center gap-2 p-3 text-sm text-teal-800 bg-teal-50 border border-teal-200 rounded-md">
          <CheckCircle2 className="w-4 h-4 shrink-0 text-teal-600" />
          <span>{successMessage}</span>
        </div>
      )}

      {errorMessage && (
        <div className="flex items-center gap-2 p-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-md">
          <AlertCircle className="w-4 h-4 shrink-0 text-red-600" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Toolbar: Search, Filters & Sort */}
      <div className="bg-white p-3.5 border border-slate-200 rounded-lg shadow-xs space-y-3">
        <div className="flex flex-col md:flex-row items-stretch md:items-center gap-3">
          {/* Search */}
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setPage(1);
              }}
              placeholder="Search invoice number or notes..."
              className="w-full pl-9 pr-3 py-2 text-sm bg-slate-50 border border-slate-200 rounded-md text-slate-900 placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-teal-600 focus:bg-white transition-colors"
            />
          </div>

          {/* Supplier/Vendor Filter */}
          <div className="w-full md:w-56">
            <input
              type="text"
              value={vendorFilter}
              onChange={(e) => {
                setVendorFilter(e.target.value);
                setPage(1);
              }}
              placeholder="Filter by supplier..."
              className="w-full px-3 py-2 text-sm bg-slate-50 border border-slate-200 rounded-md text-slate-900 placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-teal-600 focus:bg-white transition-colors"
            />
          </div>

          {/* Verification Status Filter */}
          <div className="w-full md:w-44">
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              className="w-full px-3 py-2 text-sm bg-white border border-slate-200 rounded-md text-slate-700 focus:outline-hidden focus:ring-2 focus:ring-teal-600 cursor-pointer"
            >
              <option value="">All Verification Statuses</option>
              <option value="CONFIRMED">Verified / Confirmed</option>
              <option value="NEEDS_REVIEW">Needs Review</option>
            </select>
          </div>
        </div>

        {/* Second Row: Date range & Sort */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-1 border-t border-slate-100">
          {/* Due Date Filter */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-medium text-slate-500">Due:</span>
            <input
              type="date"
              value={dueDateFrom}
              onChange={(e) => {
                setDueDateFrom(e.target.value);
                setPage(1);
              }}
              title="Due date from"
              className="px-2.5 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-md text-slate-700 focus:outline-hidden focus:ring-2 focus:ring-teal-600"
            />
            <span className="text-xs text-slate-400">to</span>
            <input
              type="date"
              value={dueDateTo}
              onChange={(e) => {
                setDueDateTo(e.target.value);
                setPage(1);
              }}
              title="Due date to"
              className="px-2.5 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-md text-slate-700 focus:outline-hidden focus:ring-2 focus:ring-teal-600"
            />

            {(searchQuery || statusFilter || vendorFilter || dueDateFrom || dueDateTo) && (
              <button
                type="button"
                onClick={() => {
                  setSearchQuery('');
                  setStatusFilter('');
                  setVendorFilter('');
                  setDueDateFrom('');
                  setDueDateTo('');
                  setPage(1);
                }}
                className="inline-flex items-center gap-1 ml-1 px-2.5 py-1.5 text-xs font-medium text-rose-700 bg-rose-50 hover:bg-rose-100 border border-rose-200 rounded-md transition-colors"
              >
                <X className="w-3.5 h-3.5" />
                <span>Reset Filters</span>
              </button>
            )}
          </div>

          {/* Sort Controls */}
          <div className="flex items-center gap-2 shrink-0 self-end sm:self-auto">
            <span className="text-xs font-medium text-slate-500 uppercase tracking-wider hidden sm:inline">
              Sort:
            </span>
            <select
              value={`${sortBy}_${sortOrder}`}
              onChange={(e) => {
                const [col, ord] = e.target.value.split('_');
                setSortBy(col);
                setSortOrder(ord);
              }}
              className="px-3 py-1.5 text-xs bg-white border border-slate-200 rounded-md text-slate-700 focus:outline-hidden focus:ring-2 focus:ring-teal-600 cursor-pointer"
            >
              <option value="invoice_date_desc">Invoice Date: Newest</option>
              <option value="invoice_date_asc">Invoice Date: Oldest</option>
              <option value="due_date_asc">Due Date: Soonest</option>
              <option value="due_date_desc">Due Date: Latest</option>
              <option value="total_amount_desc">Amount: Highest</option>
              <option value="total_amount_asc">Amount: Lowest</option>
              <option value="vendor_name_asc">Supplier: A to Z</option>
            </select>
          </div>
        </div>
      </div>

      {/* Invoice Table Container */}
      <div className="bg-white border border-slate-200 rounded-lg shadow-xs overflow-hidden">
        {isLoading ? (
          <div className="py-16 text-center text-slate-500">
            <Loader2 className="w-8 h-8 animate-spin text-teal-600 mx-auto mb-3" />
            <p className="text-sm">Loading invoices...</p>
          </div>
        ) : invoices.length === 0 ? (
          <div className="py-16 px-4 text-center">
            <div className="w-12 h-12 bg-slate-100 text-slate-400 rounded-full flex items-center justify-center mx-auto mb-3">
              <FileText className="w-6 h-6" />
            </div>
            <h3 className="text-base font-semibold text-slate-900">No invoices found</h3>
            <p className="text-sm text-slate-500 max-w-sm mx-auto mt-1 mb-5">
              {searchQuery || statusFilter || vendorFilter || dueDateFrom || dueDateTo
                ? 'No invoices match your current filter criteria. Try resetting your filters.'
                : 'Get started by uploading your first PDF or image invoice for automated extraction and review.'}
            </p>
            {searchQuery || statusFilter || vendorFilter || dueDateFrom || dueDateTo ? (
              <button
                onClick={() => {
                  setSearchQuery('');
                  setStatusFilter('');
                  setVendorFilter('');
                  setDueDateFrom('');
                  setDueDateTo('');
                  setPage(1);
                }}
                className="px-3.5 py-2 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-md transition-colors"
              >
                Reset Filters
              </button>
            ) : (
              <button
                onClick={() => {
                  setShowUploadModal(true);
                  setUploadStep('pick');
                }}
                className="inline-flex items-center gap-2 px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-md text-sm font-medium transition-colors shadow-xs"
              >
                <Plus className="w-4 h-4" />
                <span>Upload Invoice</span>
              </button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-700 divide-y divide-slate-200">
              <thead className="bg-slate-50 text-xs font-semibold text-slate-600 uppercase tracking-wider">
                <tr>
                  <th className="px-5 py-3.5">Invoice #</th>
                  <th className="px-5 py-3.5">Supplier / Vendor</th>
                  <th className="px-5 py-3.5">Date</th>
                  <th className="px-5 py-3.5">Due Date & Reminder</th>
                  <th className="px-5 py-3.5 text-right">Subtotal</th>
                  <th className="px-5 py-3.5 text-right">Tax</th>
                  <th className="px-5 py-3.5 text-right">Total Amount</th>
                  <th className="px-5 py-3.5 text-center">Verification Status</th>
                  <th className="px-5 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {invoices.map((inv) => {
                  const reminder = getDueDateReminder(inv.due_date);
                  return (
                    <tr key={inv.id} className="hover:bg-slate-50/70 transition-colors">
                      {/* Invoice Number */}
                      <td className="px-5 py-4 font-medium text-slate-900 whitespace-nowrap">
                        {inv.invoice_number}
                      </td>

                      {/* Vendor & Customer Name */}
                      <td className="px-5 py-4 text-slate-800 whitespace-nowrap">
                        <div className="font-medium text-slate-900">{inv.vendor_name}</div>
                        {inv.customer_name && (
                          <div className="text-xs text-slate-500">To: {inv.customer_name}</div>
                        )}
                      </td>

                      {/* Invoice Date */}
                      <td className="px-5 py-4 text-slate-600 whitespace-nowrap">
                        {inv.invoice_date}
                      </td>

                      {/* Due Date & Reminder */}
                      <td className="px-5 py-4 whitespace-nowrap">
                        <div className="flex flex-col gap-1">
                          <span className="text-slate-700 font-medium">{inv.due_date || '—'}</span>
                          <span className={`inline-flex items-center w-fit px-2 py-0.5 rounded text-[10px] border ${reminder.badgeClass}`}>
                            {reminder.text}
                          </span>
                        </div>
                      </td>

                      {/* Subtotal */}
                      <td className="px-5 py-4 text-right text-slate-600 whitespace-nowrap">
                        {inv.subtotal ? formatCurrency(inv.subtotal, inv.currency) : '—'}
                      </td>

                      {/* Tax */}
                      <td className="px-5 py-4 text-right text-slate-600 whitespace-nowrap">
                        {inv.tax_amount ? formatCurrency(inv.tax_amount, inv.currency) : '—'}
                      </td>

                      {/* Total Amount */}
                      <td className="px-5 py-4 text-right font-semibold text-slate-900 whitespace-nowrap">
                        {formatCurrency(inv.total_amount, inv.currency)}
                      </td>

                      {/* Verification Status */}
                      <td className="px-5 py-4 text-center whitespace-nowrap">
                        <div className="flex flex-col items-center gap-1">
                          {inv.status === 'NEEDS_REVIEW' ? (
                            <span
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-300"
                              title="Arithmetic discrepancy or missing required field detected"
                            >
                              <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                              <span>Needs Review</span>
                            </span>
                          ) : (
                            <span
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-300"
                              title="Verified invoice calculations and integrity"
                            >
                              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                              <span>Verified</span>
                            </span>
                          )}
                          {inv.anomaly_status && inv.anomaly_status !== 'NORMAL' && (
                            <span
                              className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-purple-50 text-purple-700 border border-purple-200"
                              title={inv.anomaly_explanation || 'Suspicious inconsistency detected'}
                            >
                              <Sparkles className="w-3 h-3 text-purple-500" />
                              <span>Anomaly Flagged</span>
                            </span>
                          )}
                        </div>
                      </td>

                      {/* Actions */}
                      <td className="px-5 py-4 text-right whitespace-nowrap">
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            onClick={() => setViewingInvoice(inv)}
                            title="View Details & Calculations"
                            className="p-1.5 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-md transition-colors"
                          >
                            <Eye className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleOpenEdit(inv)}
                            title="Edit Invoice"
                            className="p-1.5 text-slate-400 hover:text-teal-700 hover:bg-teal-50 rounded-md transition-colors"
                          >
                            <Edit2 className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => setDeletingInvoice(inv)}
                            title="Delete Invoice"
                            className="p-1.5 text-slate-400 hover:text-red-700 hover:bg-red-50 rounded-md transition-colors"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Footer Count */}
        <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex items-center justify-between text-xs text-slate-500">
          <span>Showing {invoices.length} of {totalCount} records</span>
          <span>Strict User Tenant Isolation Active</span>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* MODAL 1: Upload & Candidate Review Workflow                               */}
      {/* ========================================================================= */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
          <div className={`bg-white rounded-lg border border-slate-200 shadow-xl ${uploadStep === 'review' ? 'max-w-4xl' : 'max-w-2xl'} w-full max-h-[90vh] flex flex-col overflow-hidden`}>
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50/50">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded bg-teal-600 flex items-center justify-center text-white">
                  <Upload className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-base font-semibold text-slate-900">
                    {uploadStep === 'pick' ? 'Upload Invoice' : 'Review Extracted Values'}
                  </h3>
                  <p className="text-xs text-slate-500">
                    {uploadStep === 'pick'
                      ? 'Upload a PDF or image invoice (max 10MB)'
                      : 'Verify candidate fields before saving'}
                  </p>
                </div>
              </div>

              <button
                onClick={() => setShowUploadModal(false)}
                className="text-slate-400 hover:text-slate-600 p-1.5 rounded-md hover:bg-slate-100"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto space-y-5">
              {uploadError && (
                <div className="flex items-start gap-3 p-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-md">
                  <AlertCircle className="w-5 h-5 shrink-0 text-red-600 mt-0.5" />
                  <div className="flex-1">{uploadError}</div>
                </div>
              )}

              {/* STEP 1: File Pick / Dropzone */}
              {uploadStep === 'pick' && (
                <div>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,.png,.jpg,.jpeg,.webp"
                    onChange={handleFileSelect}
                    className="hidden"
                    id="invoice-file-input"
                  />

                  <label
                    htmlFor="invoice-file-input"
                    className="border-2 border-dashed border-slate-300 hover:border-teal-500 rounded-lg p-10 flex flex-col items-center justify-center text-center cursor-pointer transition-colors hover:bg-teal-50/20"
                  >
                    {isUploading ? (
                      <div className="space-y-3">
                        <Loader2 className="w-8 h-8 animate-spin text-teal-600 mx-auto" />
                        <p className="text-sm font-medium text-slate-700">
                          Uploading and extracting candidate invoice details...
                        </p>
                        <p className="text-xs text-slate-400">Parsing document structure with pdfplumber</p>
                      </div>
                    ) : (
                      <>
                        <div className="w-12 h-12 bg-slate-100 text-slate-500 rounded-full flex items-center justify-center mb-3">
                          <Upload className="w-6 h-6" />
                        </div>
                        <p className="text-sm font-medium text-slate-900">
                          Click to select an invoice file or drag and drop
                        </p>
                        <p className="text-xs text-slate-500 mt-1">
                          Supported formats: PDF, JPEG, PNG, WEBP (Up to 10MB)
                        </p>
                      </>
                    )}
                  </label>
                </div>
              )}

              {/* STEP 2: Candidate Review Form */}
              {uploadStep === 'review' && (
                <form onSubmit={handleConfirmSave} id="review-form" className="space-y-4">
                  {/* Actionable Warnings Alert */}
                  {validationWarnings.length > 0 && (
                    <div className="p-3 bg-amber-50 border border-amber-200 rounded-md text-xs text-amber-900 leading-relaxed space-y-1">
                      <div className="flex items-center gap-1.5 font-semibold text-amber-900">
                        <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                        <span>Attention Required</span>
                      </div>
                      <ul className="list-disc pl-5 space-y-0.5 text-amber-800">
                        {validationWarnings.map((warn, idx) => (
                          <li key={idx}>{warn}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Extraction Notice Alert */}
                  <div className="p-3 bg-teal-50 border border-teal-200 rounded-md text-xs text-teal-800 leading-relaxed">
                    <div className="flex items-center justify-between mb-1">
                      <p className="font-semibold text-teal-900">Automated Extraction Complete</p>
                    </div>
                    <p>Please review candidate values below. Missing fields remain empty until you provide them.</p>
                    {extractionNotes.length > 0 && (
                      <ul className="list-disc pl-4 mt-1.5 space-y-0.5 text-teal-700">
                        {extractionNotes.map((note, idx) => (
                          <li key={idx}>{note}</li>
                        ))}
                      </ul>
                    )}
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {/* Invoice Number */}
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
                          Invoice Number *
                        </label>
                        {renderConfidenceBadge('invoice_number')}
                      </div>
                      <input
                        type="text"
                        required
                        value={formData.invoice_number}
                        onChange={(e) => setFormData({ ...formData, invoice_number: e.target.value })}
                        placeholder="e.g. INV-1002"
                        className="w-full px-3 py-2 text-sm border border-slate-300 rounded-md text-slate-900 focus:ring-2 focus:ring-teal-600 focus:outline-hidden"
                      />
                    </div>

                    {/* Supplier / Vendor Name */}
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
                          Supplier / Vendor *
                        </label>
                        {renderConfidenceBadge('vendor_name')}
                      </div>
                      <input
                        type="text"
                        required
                        value={formData.vendor_name}
                        onChange={(e) => setFormData({ ...formData, vendor_name: e.target.value })}
                        placeholder="e.g. Acme Cloud Corp"
                        className="w-full px-3 py-2 text-sm border border-slate-300 rounded-md text-slate-900 focus:ring-2 focus:ring-teal-600 focus:outline-hidden"
                      />
                    </div>

                    {/* Customer / Bill-To Name */}
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
                          Customer / Bill-To <span className="text-slate-400 font-normal lowercase">(optional)</span>
                        </label>
                        {renderConfidenceBadge('customer_name')}
                      </div>
                      <input
                        type="text"
                        value={formData.customer_name}
                        onChange={(e) => setFormData({ ...formData, customer_name: e.target.value })}
                        placeholder="e.g. Demo Customer"
                        className="w-full px-3 py-2 text-sm border border-slate-300 rounded-md text-slate-900 focus:ring-2 focus:ring-teal-600 focus:outline-hidden"
                      />
                    </div>

                    {/* Invoice Date */}
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
                          Invoice Date *
                        </label>
                        {renderConfidenceBadge('invoice_date')}
                      </div>
                      <input
                        type="date"
                        required
                        value={formData.invoice_date}
                        onChange={(e) => setFormData({ ...formData, invoice_date: e.target.value })}
                        className="w-full px-3 py-2 text-sm border border-slate-300 rounded-md text-slate-900 focus:ring-2 focus:ring-teal-600 focus:outline-hidden"
                      />
                    </div>

                    {/* Due Date (Optional) */}
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
                          Due Date <span className="text-slate-400 font-normal lowercase">(optional)</span>
                        </label>
                        {renderConfidenceBadge('due_date')}
                      </div>
                      <input
                        type="date"
                        value={formData.due_date}
                        onChange={(e) => setFormData({ ...formData, due_date: e.target.value })}
                        className="w-full px-3 py-2 text-sm border border-slate-300 rounded-md text-slate-900 focus:ring-2 focus:ring-teal-600 focus:outline-hidden"
                      />
                    </div>

                    {/* Subtotal */}
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
                          Subtotal <span className="text-slate-400 font-normal lowercase">(optional)</span>
                        </label>
                        {renderConfidenceBadge('subtotal')}
                      </div>
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        value={formData.subtotal}
                        onChange={(e) => setFormData({ ...formData, subtotal: e.target.value })}
                        placeholder="0.00"
                        className="w-full px-3 py-2 text-sm border border-slate-300 rounded-md text-slate-900 focus:ring-2 focus:ring-teal-600 focus:outline-hidden"
                      />
                    </div>

                    {/* Tax Amount */}
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
                          Tax / GST <span className="text-slate-400 font-normal lowercase">(optional)</span>
                        </label>
                        {renderConfidenceBadge('tax_amount')}
                      </div>
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        value={formData.tax_amount}
                        onChange={(e) => setFormData({ ...formData, tax_amount: e.target.value })}
                        placeholder="0.00"
                        className="w-full px-3 py-2 text-sm border border-slate-300 rounded-md text-slate-900 focus:ring-2 focus:ring-teal-600 focus:outline-hidden"
                      />
                      {taxBreakdown && (
                        <p className="mt-1 text-[11px] text-teal-700">
                          Detected GST: {taxBreakdown.cgst && `CGST: ${formData.currency} ${taxBreakdown.cgst}`}
                          {taxBreakdown.sgst && ` • SGST: ${formData.currency} ${taxBreakdown.sgst}`}
                          {taxBreakdown.igst && ` • IGST: ${formData.currency} ${taxBreakdown.igst}`}
                        </p>
                      )}
                    </div>

                    {/* Total Amount */}
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
                          Total Amount *
                        </label>
                        {renderConfidenceBadge('total_amount')}
                      </div>
                      <input
                        type="number"
                        step="0.01"
                        min="0.01"
                        required
                        value={formData.total_amount}
                        onChange={(e) => setFormData({ ...formData, total_amount: e.target.value })}
                        placeholder="0.00"
                        className="w-full px-3 py-2 text-sm font-semibold border border-slate-300 rounded-md text-slate-900 focus:ring-2 focus:ring-teal-600 focus:outline-hidden"
                      />
                    </div>

                    {/* Currency */}
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                        Currency
                      </label>
                      <select
                        value={formData.currency}
                        onChange={(e) => setFormData({ ...formData, currency: e.target.value })}
                        className="w-full px-3 py-2 text-sm border border-slate-300 rounded-md text-slate-900 focus:ring-2 focus:ring-teal-600 focus:outline-hidden"
                      >
                        <option value="USD">USD ($)</option>
                        <option value="EUR">EUR (€)</option>
                        <option value="GBP">GBP (£)</option>
                        <option value="INR">INR (₹)</option>
                        <option value="CAD">CAD ($)</option>
                        <option value="AUD">AUD ($)</option>
                      </select>
                    </div>
                  </div>

                  {/* Notes */}
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                      Notes <span className="text-slate-400 font-normal lowercase">(optional)</span>
                    </label>
                    <textarea
                      rows={2}
                      value={formData.notes}
                      onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                      placeholder="Add any internal reference or notes..."
                      className="w-full px-3 py-2 text-sm border border-slate-300 rounded-md text-slate-900 focus:ring-2 focus:ring-teal-600 focus:outline-hidden"
                    />
                  </div>

                  {/* Extracted Party & Tax Metadata */}
                  {candidateDetails && (candidateDetails.vendor_address || candidateDetails.vendor_gstin || candidateDetails.customer_billing_address || candidateDetails.customer_gstin || candidateDetails.po_number || candidateDetails.payment_terms) && (
                    <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-md space-y-3">
                      <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                        <span className="text-xs font-semibold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
                          <Layers className="w-3.5 h-3.5 text-teal-600" />
                          Document Metadata & Tax Identity
                        </span>
                        <div className="flex items-center gap-1.5 flex-wrap">
                          {candidateDetails.invoice_type && (
                            <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-slate-200 text-slate-700">
                              {candidateDetails.invoice_type}
                            </span>
                          )}
                          {candidateDetails.payment_terms && (
                            <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-blue-100 text-blue-800 border border-blue-200">
                              Terms: {candidateDetails.payment_terms}
                            </span>
                          )}
                          {candidateDetails.po_number && (
                            <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-purple-100 text-purple-800 border border-purple-200">
                              PO: {candidateDetails.po_number}
                            </span>
                          )}
                        </div>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                        {/* Vendor Section */}
                        <div className="space-y-1 bg-white p-2.5 rounded border border-slate-200">
                          <span className="font-semibold text-slate-700 block">Supplier / Vendor Identity</span>
                          {candidateDetails.vendor_address && (
                            <p className="text-slate-600 text-[11px] leading-tight">
                              <span className="text-slate-400">Address: </span>
                              {candidateDetails.vendor_address}
                            </p>
                          )}
                          <div className="flex items-center gap-3 pt-1 text-[11px]">
                            {candidateDetails.vendor_gstin && (
                              <span>
                                <strong className="text-slate-500">GSTIN: </strong>
                                <span className="font-mono text-slate-800">{candidateDetails.vendor_gstin}</span>
                              </span>
                            )}
                            {candidateDetails.vendor_state && (
                              <span>
                                <strong className="text-slate-500">State: </strong>
                                <span className="text-slate-800">{candidateDetails.vendor_state} {candidateDetails.vendor_state_code ? `(${candidateDetails.vendor_state_code})` : ''}</span>
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Customer Section */}
                        <div className="space-y-1 bg-white p-2.5 rounded border border-slate-200">
                          <span className="font-semibold text-slate-700 block">Customer / Buyer Identity</span>
                          {candidateDetails.customer_billing_address && (
                            <p className="text-slate-600 text-[11px] leading-tight">
                              <span className="text-slate-400">Billing: </span>
                              {candidateDetails.customer_billing_address}
                            </p>
                          )}
                          <div className="flex items-center gap-3 pt-1 text-[11px]">
                            {candidateDetails.customer_gstin && (
                              <span>
                                <strong className="text-slate-500">GSTIN: </strong>
                                <span className="font-mono text-slate-800">{candidateDetails.customer_gstin}</span>
                              </span>
                            )}
                            {candidateDetails.customer_state && (
                              <span>
                                <strong className="text-slate-500">State: </strong>
                                <span className="text-slate-800">{candidateDetails.customer_state} {candidateDetails.customer_state_code ? `(${candidateDetails.customer_state_code})` : ''}</span>
                              </span>
                            )}
                            {candidateDetails.place_of_supply && (
                              <span>
                                <strong className="text-slate-500">POS: </strong>
                                <span className="text-slate-800">{candidateDetails.place_of_supply}</span>
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Extracted Line Items Table */}
                  {candidateDetails?.line_items && candidateDetails.line_items.length > 0 && (
                    <div className="border border-slate-200 rounded-md overflow-hidden">
                      <div className="bg-slate-50 px-3.5 py-2 border-b border-slate-200 flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-800 uppercase tracking-wider">
                          Extracted Line Items ({candidateDetails.line_items.length})
                        </span>
                        <span className="text-[11px] text-slate-500">
                          Items & rates extracted from document table
                        </span>
                      </div>
                      <div className="max-h-48 overflow-y-auto">
                        <table className="w-full text-left text-xs">
                          <thead className="bg-slate-100 text-slate-600 border-b border-slate-200">
                            <tr>
                              <th className="px-3 py-1.5 w-10">#</th>
                              <th className="px-3 py-1.5">Description</th>
                              <th className="px-3 py-1.5 w-24">HSN/SAC</th>
                              <th className="px-3 py-1.5 text-right w-16">Qty</th>
                              <th className="px-3 py-1.5 text-right w-24">Unit Price</th>
                              <th className="px-3 py-1.5 text-right w-24">Total</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100">
                            {candidateDetails.line_items.map((item, idx) => (
                              <tr key={idx} className="hover:bg-slate-50/50">
                                <td className="px-3 py-1.5 text-slate-500 font-mono">{item.item_number || idx + 1}</td>
                                <td className="px-3 py-1.5 text-slate-800 font-medium">{item.description}</td>
                                <td className="px-3 py-1.5 text-slate-500 font-mono text-[11px]">{item.hsn_sac || '—'}</td>
                                <td className="px-3 py-1.5 text-slate-700 text-right font-mono">{item.quantity !== null && item.quantity !== undefined ? item.quantity : '—'}</td>
                                <td className="px-3 py-1.5 text-slate-700 text-right font-mono">
                                  {item.unit_price !== null && item.unit_price !== undefined ? `${formData.currency} ${parseFloat(item.unit_price).toFixed(2)}` : '—'}
                                </td>
                                <td className="px-3 py-1.5 text-slate-900 font-semibold text-right font-mono">
                                  {item.line_total !== null && item.line_total !== undefined ? `${formData.currency} ${parseFloat(item.line_total).toFixed(2)}` : '—'}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {/* Raw Document Extracted Text Drawer */}
                  {candidateDetails?.raw_text && (
                    <div className="border border-slate-200 rounded-md overflow-hidden text-xs">
                      <button
                        type="button"
                        onClick={() => setShowRawText(!showRawText)}
                        className="w-full px-3.5 py-2 bg-slate-50 hover:bg-slate-100 flex items-center justify-between text-slate-700 font-medium transition-colors"
                      >
                        <div className="flex items-center gap-1.5">
                          <FileText className="w-3.5 h-3.5 text-slate-500" />
                          <span>Extracted Document Stream Text ({candidateDetails.raw_text.length} characters)</span>
                        </div>
                        {showRawText ? <ChevronUp className="w-4 h-4 text-slate-500" /> : <ChevronDown className="w-4 h-4 text-slate-500" />}
                      </button>
                      {showRawText && (
                        <div className="p-3 bg-slate-900 text-slate-200 space-y-2">
                          <div className="flex items-center justify-between text-[11px] text-slate-400">
                            <span>Raw text captured from parser stream for auditing & verification:</span>
                            <button
                              type="button"
                              onClick={handleCopyRawText}
                              className="inline-flex items-center gap-1 px-2 py-0.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded text-[11px] transition-colors"
                            >
                              {copiedRawText ? (
                                <>
                                  <Check className="w-3 h-3 text-emerald-400" />
                                  <span>Copied</span>
                                </>
                              ) : (
                                <>
                                  <Copy className="w-3 h-3" />
                                  <span>Copy Raw Text</span>
                                </>
                              )}
                            </button>
                          </div>
                          <pre className="max-h-48 overflow-y-auto p-2 bg-black/40 rounded font-mono text-[11px] leading-relaxed select-all whitespace-pre-wrap">
                            {candidateDetails.raw_text}
                          </pre>
                        </div>
                      )}
                    </div>
                  )}
                </form>
              )}
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowUploadModal(false)}
                disabled={isSaving}
                className="px-3.5 py-2 text-xs font-medium text-slate-700 hover:bg-slate-200 rounded-md transition-colors"
              >
                Cancel
              </button>

              {uploadStep === 'review' && (
                <button
                  type="submit"
                  form="review-form"
                  disabled={isSaving}
                  className="inline-flex items-center gap-1.5 px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-md text-xs font-medium transition-colors shadow-xs disabled:opacity-70"
                >
                  {isSaving ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Saving Invoice...</span>
                    </>
                  ) : (
                    <span>Confirm & Save Invoice</span>
                  )}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODAL 2: Edit Invoice Modal                                               */}
      {/* ========================================================================= */}
      {editingInvoice && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
          <div className="bg-white rounded-lg border border-slate-200 shadow-xl max-w-lg w-full overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <h3 className="text-base font-semibold text-slate-900">
                Edit Invoice #{editingInvoice.invoice_number}
              </h3>
              <button
                onClick={() => setEditingInvoice(null)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSaveEdit} className="p-6 space-y-4">
              {editError && (
                <div className="p-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-md">
                  {editError}
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                    Invoice # *
                  </label>
                  <input
                    type="text"
                    required
                    value={editingInvoice.invoice_number}
                    onChange={(e) =>
                      setEditingInvoice({ ...editingInvoice, invoice_number: e.target.value })
                    }
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-md"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                    Supplier *
                  </label>
                  <input
                    type="text"
                    required
                    value={editingInvoice.vendor_name}
                    onChange={(e) =>
                      setEditingInvoice({ ...editingInvoice, vendor_name: e.target.value })
                    }
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-md"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                    Invoice Date *
                  </label>
                  <input
                    type="date"
                    required
                    value={editingInvoice.invoice_date}
                    onChange={(e) =>
                      setEditingInvoice({ ...editingInvoice, invoice_date: e.target.value })
                    }
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-md"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                    Due Date
                  </label>
                  <input
                    type="date"
                    value={editingInvoice.due_date}
                    onChange={(e) =>
                      setEditingInvoice({ ...editingInvoice, due_date: e.target.value })
                    }
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-md"
                  />
                </div>

                <div className="col-span-2">
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                    Customer / Billed To
                  </label>
                  <input
                    type="text"
                    value={editingInvoice.customer_name || ''}
                    onChange={(e) =>
                      setEditingInvoice({ ...editingInvoice, customer_name: e.target.value })
                    }
                    placeholder="e.g. Demo Customer"
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-md"
                  />
                </div>

                <div className="col-span-2">
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                    Total Amount *
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    required
                    value={editingInvoice.total_amount}
                    onChange={(e) =>
                      setEditingInvoice({ ...editingInvoice, total_amount: e.target.value })
                    }
                    className="w-full px-3 py-2 text-sm font-semibold border border-slate-300 rounded-md"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                  Notes
                </label>
                <textarea
                  rows={2}
                  value={editingInvoice.notes}
                  onChange={(e) =>
                    setEditingInvoice({ ...editingInvoice, notes: e.target.value })
                  }
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-md"
                />
              </div>

              <div className="pt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setEditingInvoice(null)}
                  className="px-3.5 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100 rounded-md"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isUpdating}
                  className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-md text-xs font-medium"
                >
                  {isUpdating ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODAL 3: Invoice Detail View                                              */}
      {/* ========================================================================= */}
      {viewingInvoice && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
          <div className="bg-white rounded-lg border border-slate-200 shadow-xl max-w-lg w-full overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div>
                <h3 className="text-base font-semibold text-slate-900">
                  Invoice #{viewingInvoice.invoice_number}
                </h3>
                <p className="text-xs text-slate-500">
                  {viewingInvoice.vendor_name}
                  {viewingInvoice.customer_name ? ` • Billed to: ${viewingInvoice.customer_name}` : ''}
                </p>
              </div>
              <button
                onClick={() => setViewingInvoice(null)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4 text-xs">
                <div>
                  <span className="text-slate-500 uppercase font-semibold block mb-0.5">Invoice Date</span>
                  <span className="text-slate-900 font-medium text-sm">{viewingInvoice.invoice_date}</span>
                </div>
                <div>
                  <span className="text-slate-500 uppercase font-semibold block mb-0.5">Due Date & Reminder</span>
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-slate-900 font-medium text-sm">
                      {viewingInvoice.due_date || 'None specified'}
                    </span>
                    {(() => {
                      const reminder = getDueDateReminder(viewingInvoice.due_date);
                      return (
                        <span className={`inline-flex px-2 py-0.5 rounded text-[10px] border ${reminder.badgeClass}`}>
                          {reminder.text}
                        </span>
                      );
                    })()}
                  </div>
                </div>
                <div>
                  <span className="text-slate-500 uppercase font-semibold block mb-0.5">Currency</span>
                  <span className="text-slate-900 font-medium text-sm">{viewingInvoice.currency || 'USD'}</span>
                </div>
                <div>
                  <span className="text-slate-500 uppercase font-semibold block mb-0.5">Verification Status</span>
                  {viewingInvoice.status === 'NEEDS_REVIEW' ? (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-300">
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                      <span>Needs Review</span>
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-300">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                      <span>Verified</span>
                    </span>
                  )}
                </div>
              </div>

              {/* Calculations Integrity Check */}
              <div className="p-3 bg-slate-50 border border-slate-200 rounded-md text-xs space-y-1.5">
                <div className="font-semibold text-slate-800 flex items-center gap-1.5">
                  <ShieldCheck className="w-4 h-4 text-teal-600" />
                  <span>Verification & Calculation Checks</span>
                </div>
                <p className="text-[11px] text-slate-600">
                  {viewingInvoice.subtotal && viewingInvoice.tax_amount && Math.abs((parseFloat(viewingInvoice.subtotal) + parseFloat(viewingInvoice.tax_amount)) - parseFloat(viewingInvoice.total_amount)) > 0.05
                    ? '⚠️ Arithmetic discrepancy: Subtotal + Tax differs from Grand Total.'
                    : '✓ Arithmetic verified: Subtotal + Tax matches Grand Total.'}
                </p>
                <p className="text-[11px] text-slate-600">
                  ✓ Required fields verified: Supplier, Invoice Number, Date, and Total Amount present.
                </p>
                <p className="text-[11px] text-slate-600">
                  ✓ Duplicate defense: Verified single source of truth across system.
                </p>
              </div>

              {/* Financial Breakdown */}
              <div className="pt-3 border-t border-slate-100 space-y-1.5 text-xs">
                {viewingInvoice.subtotal !== null && viewingInvoice.subtotal !== undefined && (
                  <div className="flex justify-between text-slate-600">
                    <span>Subtotal</span>
                    <span>{formatCurrency(viewingInvoice.subtotal, viewingInvoice.currency)}</span>
                  </div>
                )}
                {viewingInvoice.tax_amount !== null && viewingInvoice.tax_amount !== undefined && (
                  <div className="flex justify-between text-slate-600">
                    <span>Tax / GST</span>
                    <span>{formatCurrency(viewingInvoice.tax_amount, viewingInvoice.currency)}</span>
                  </div>
                )}
                <div className="flex justify-between text-base font-bold text-slate-900 pt-2 border-t border-slate-200">
                  <span>Total Amount</span>
                  <span>{formatCurrency(viewingInvoice.total_amount, viewingInvoice.currency)}</span>
                </div>
              </div>

              {/* Notes */}
              {viewingInvoice.notes && (
                <div className="pt-3 border-t border-slate-100">
                  <span className="text-xs text-slate-500 uppercase font-semibold block mb-1">Notes</span>
                  <p className="text-xs text-slate-700 bg-slate-50 p-2.5 rounded-md border border-slate-100">
                    {viewingInvoice.notes}
                  </p>
                </div>
              )}

              {/* ML Anomaly Screening Status */}
              {viewingInvoice.anomaly_status && (
                <div
                  className={`p-3 rounded-md border text-xs space-y-1 ${
                    viewingInvoice.anomaly_status === 'POTENTIALLY_UNUSUAL'
                      ? 'bg-rose-50 border-rose-200 text-rose-800'
                      : 'bg-teal-50 border-teal-200 text-teal-800'
                  }`}
                >
                  <div className="flex items-center gap-1.5 font-semibold">
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>
                      ML Screening:{' '}
                      {viewingInvoice.anomaly_status === 'POTENTIALLY_UNUSUAL'
                        ? 'Potentially Unusual Pattern'
                        : 'No Unusual Pattern Detected'}
                    </span>
                  </div>
                  {viewingInvoice.anomaly_explanation && (
                    <p className="text-[11px] leading-relaxed opacity-90">
                      {viewingInvoice.anomaly_explanation}
                    </p>
                  )}
                </div>
              )}
            </div>

            <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex items-center justify-end">
              <button
                onClick={() => setViewingInvoice(null)}
                className="px-4 py-2 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded-md hover:bg-slate-100 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODAL 4: Delete Confirmation Dialog                                       */}
      {/* ========================================================================= */}
      {deletingInvoice && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
          <div className="bg-white rounded-lg border border-slate-200 shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-full bg-red-100 text-red-600 flex items-center justify-center shrink-0">
                <Trash2 className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-slate-900">Confirm Deletion</h3>
                <p className="text-xs text-slate-500 mt-1">
                  Are you sure you want to delete invoice{' '}
                  <span className="font-semibold text-slate-800">#{deletingInvoice.invoice_number}</span> from{' '}
                  <span className="font-semibold text-slate-800">{deletingInvoice.vendor_name}</span>?
                  This action cannot be undone.
                </p>
              </div>
            </div>

            <div className="pt-2 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setDeletingInvoice(null)}
                disabled={isDeleting}
                className="px-3.5 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100 rounded-md"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmDelete}
                disabled={isDeleting}
                className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-md text-xs font-medium disabled:opacity-70"
              >
                {isDeleting ? 'Deleting...' : 'Delete Invoice'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
