import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  BarChart3,
  Download,
  Calendar,
  Building,
  DollarSign,
  FileText,
  AlertCircle,
  AlertTriangle,
  Filter,
  RefreshCw,
  Loader2,
  FileDown,
  ShieldCheck,
  CheckCircle2,
  Scale,
  ArrowRight,
  Clock,
  Layers,
  ChevronRight,
  ExternalLink,
  Info,
} from 'lucide-react';
import {
  getReportsAnalytics,
  downloadInvoicesCsv,
  downloadReconciliationCsv,
  downloadReportPdf,
} from '../api/reports';
import { getDueDateReminder } from '../utils/dueDateHelper';

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

export default function Reports() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Tab State: 'invoices' | 'verification' | 'mismatches' | 'ledger' | 'expenses' | 'charts'
  const initialTab = searchParams.get('tab') || 'invoices';
  const [activeTab, setActiveTab] = useState(initialTab);

  // Analytics Data & Loading
  const [reportsData, setReportsData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [downloadingType, setDownloadingType] = useState(null);

  // Filters
  const [datePreset, setDatePreset] = useState('all');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [vendorFilter, setVendorFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  // Synchronize Tab with URL query param
  useEffect(() => {
    const tabParam = searchParams.get('tab');
    if (tabParam && tabParam !== activeTab) {
      setActiveTab(tabParam);
    }
  }, [searchParams]);

  const handleTabChange = (newTab) => {
    setActiveTab(newTab);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('tab', newTab);
      return next;
    });
  };

  // Date Presets
  const handlePresetChange = (preset) => {
    setDatePreset(preset);
    const now = new Date();
    if (preset === 'all') {
      setStartDate('');
      setEndDate('');
    } else if (preset === 'this_month') {
      const start = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split('T')[0];
      const end = new Date(now.getFullYear(), now.getMonth() + 1, 0).toISOString().split('T')[0];
      setStartDate(start);
      setEndDate(end);
    } else if (preset === 'last_month') {
      const start = new Date(now.getFullYear(), now.getMonth() - 1, 1).toISOString().split('T')[0];
      const end = new Date(now.getFullYear(), now.getMonth(), 0).toISOString().split('T')[0];
      setStartDate(start);
      setEndDate(end);
    } else if (preset === 'this_year') {
      const start = new Date(now.getFullYear(), 0, 1).toISOString().split('T')[0];
      const end = new Date(now.getFullYear(), 11, 31).toISOString().split('T')[0];
      setStartDate(start);
      setEndDate(end);
    }
  };

  const fetchReports = useCallback(async () => {
    if (startDate && endDate && startDate > endDate) {
      setErrorMessage('Start date cannot be after end date.');
      return;
    }

    setIsLoading(true);
    setErrorMessage('');
    try {
      const res = await getReportsAnalytics({
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        vendor: vendorFilter.trim() || undefined,
      });
      setReportsData(res);
    } catch (err) {
      setErrorMessage(err.message || 'Failed to load reports analysis.');
    } finally {
      setIsLoading(false);
    }
  }, [startDate, endDate, vendorFilter]);

  useEffect(() => {
    fetchReports();
  }, [fetchReports]);

  const handleResetFilters = () => {
    setDatePreset('all');
    setStartDate('');
    setEndDate('');
    setVendorFilter('');
    setStatusFilter('');
  };

  const handleDownload = async (type) => {
    setDownloadingType(type);
    setErrorMessage('');
    setSuccessMessage('');
    try {
      const params = {
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        vendor: vendorFilter.trim() || undefined,
      };

      if (type === 'pdf') {
        await downloadReportPdf(params);
        setSuccessMessage('Executive summary PDF report downloaded successfully.');
      } else if (type === 'invoices') {
        await downloadInvoicesCsv(params);
        setSuccessMessage('Invoices CSV export downloaded successfully.');
      } else if (type === 'reconciliation') {
        await downloadReconciliationCsv(params);
        setSuccessMessage('Reconciliation CSV export downloaded successfully.');
      }
      setTimeout(() => setSuccessMessage(''), 4000);
    } catch (err) {
      setErrorMessage(err.message || `Failed to export ${type.toUpperCase()}.`);
    } finally {
      setDownloadingType(null);
    }
  };

  // Base data elements
  const allInvoices = reportsData?.invoices || [];
  const reconciliationItems = reportsData?.reconciliation_items || [];
  const reconSummary = reportsData?.reconciliation_summary || {
    matched_count: 0,
    mismatch_count: 0,
    missing_count: 0,
    total_records: 0,
  };
  const summary = reportsData?.summary || {
    total_invoices_count: 0,
    total_invoiced_amount: '0.00',
    currency: 'USD',
  };
  const monthlyTrends = reportsData?.monthly_trends || [];

  // Client-side status filtering for Section A (Invoice Report)
  const filteredInvoices = useMemo(() => {
    if (!statusFilter) return allInvoices;
    return allInvoices.filter((inv) => {
      if (statusFilter === 'CONFIRMED') {
        return inv.verification_status === 'CONFIRMED';
      }
      if (statusFilter === 'NEEDS_REVIEW') {
        return (
          inv.verification_status === 'NEEDS_REVIEW' ||
          (inv.anomaly_status && inv.anomaly_status !== 'NORMAL')
        );
      }
      return true;
    });
  }, [allInvoices, statusFilter]);

  // Section B (Verification Analysis) calculation breakdown
  const verificationBreakdown = useMemo(() => {
    let verifiedCount = 0;
    let mismatchesCount = 0;
    let needsReviewCount = 0;
    let missingFieldsCount = 0;
    let duplicateWarningsCount = 0;
    let calcInconsistenciesCount = 0;

    const flaggedInvoices = [];

    allInvoices.forEach((inv) => {
      let isFlagged = false;
      const issues = [];

      const isConfirmed = inv.verification_status === 'CONFIRMED';
      if (isConfirmed && (!inv.anomaly_status || inv.anomaly_status === 'NORMAL')) {
        verifiedCount++;
      } else {
        needsReviewCount++;
      }

      // 1. Missing Required Fields Check
      if (!inv.due_date) {
        missingFieldsCount++;
        isFlagged = true;
        issues.push({
          field: 'Due Date',
          type: 'Missing Field',
          description: 'Due date is not recorded or was not detected on original invoice document.',
        });
      }

      // 2. Calculation & Tax Inconsistencies Check
      if (inv.subtotal != null && inv.total_amount != null) {
        const sub = parseFloat(inv.subtotal || 0);
        const tax = parseFloat(inv.tax_amount || 0);
        const grand = parseFloat(inv.total_amount || 0);
        const expected = sub + tax;
        if (Math.abs(expected - grand) > 0.05) {
          calcInconsistenciesCount++;
          mismatchesCount++;
          isFlagged = true;
          issues.push({
            field: 'Subtotal & Tax Calculation',
            type: 'Arithmetic Mismatch',
            description: `Subtotal (${formatCurrency(sub, inv.currency)}) + Tax (${formatCurrency(tax, inv.currency)}) = ${formatCurrency(expected, inv.currency)}, differing from Grand Total (${formatCurrency(grand, inv.currency)}).`,
          });
        }
      }

      // 3. Duplicate Warning Check
      if (inv.notes && inv.notes.toLowerCase().includes('duplicate')) {
        duplicateWarningsCount++;
        mismatchesCount++;
        isFlagged = true;
        issues.push({
          field: 'Invoice Number',
          type: 'Duplicate Warning',
          description: 'Potential duplicate invoice detected with existing vendor record.',
        });
      }

      // 4. ML Screening Flag
      if (inv.anomaly_status && inv.anomaly_status !== 'NORMAL') {
        mismatchesCount++;
        isFlagged = true;
        issues.push({
          field: 'Pattern Screening',
          type: 'Anomaly Detected',
          description: inv.anomaly_explanation || 'Unusual pattern in amount, vendor, or posting interval flagged by ML screening.',
        });
      }

      if (isFlagged) {
        flaggedInvoices.push({
          ...inv,
          issues,
        });
      }
    });

    return {
      verifiedCount,
      mismatchesCount,
      needsReviewCount,
      missingFieldsCount,
      duplicateWarningsCount,
      calcInconsistenciesCount,
      flaggedInvoices,
    };
  }, [allInvoices]);

  // Section C (Mismatch Analysis) items
  const mismatchRecords = useMemo(() => {
    return reconciliationItems.filter(
      (item) => item.match_status !== 'MATCH' && item.match_status !== 'MATCHED'
    );
  }, [reconciliationItems]);

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Reports & Analysis</h1>
          <p className="text-sm text-slate-500 mt-1">
            In-depth audit of extracted invoices, calculation integrity, mismatch analysis, and ledger reconciliation.
          </p>
        </div>

        {/* Global Export Actions */}
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => handleDownload('invoices')}
            disabled={downloadingType === 'invoices'}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 rounded text-xs font-semibold transition-colors shadow-xs disabled:opacity-50"
          >
            {downloadingType === 'invoices' ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Download className="w-3.5 h-3.5 text-slate-500" />
            )}
            <span>Export Invoices CSV</span>
          </button>

          <button
            onClick={() => handleDownload('reconciliation')}
            disabled={downloadingType === 'reconciliation'}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 rounded text-xs font-semibold transition-colors shadow-xs disabled:opacity-50"
          >
            {downloadingType === 'reconciliation' ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Download className="w-3.5 h-3.5 text-slate-500" />
            )}
            <span>Export Ledger CSV</span>
          </button>

          <button
            onClick={() => handleDownload('pdf')}
            disabled={downloadingType === 'pdf'}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-teal-600 hover:bg-teal-700 text-white rounded text-xs font-semibold transition-colors shadow-xs disabled:opacity-50"
          >
            {downloadingType === 'pdf' ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <FileDown className="w-3.5 h-3.5" />
            )}
            <span>Export Summary PDF</span>
          </button>
        </div>
      </div>

      {/* Notifications */}
      {successMessage && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-md text-xs text-emerald-800 flex items-center justify-between">
          <span>{successMessage}</span>
          <button onClick={() => setSuccessMessage('')} className="text-emerald-600 font-bold ml-2">
            &times;
          </button>
        </div>
      )}
      {errorMessage && (
        <div className="p-3 bg-rose-50 border border-rose-200 rounded-md text-xs text-rose-800 flex items-center justify-between">
          <span>{errorMessage}</span>
          <button onClick={() => setErrorMessage('')} className="text-rose-600 font-bold ml-2">
            &times;
          </button>
        </div>
      )}

      {/* Filter Toolbar */}
      <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-xs space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
          {/* Date Presets */}
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="font-semibold text-slate-700">Period:</span>
            {['all', 'this_month', 'last_month', 'this_year', 'custom'].map((p) => (
              <button
                key={p}
                onClick={() => handlePresetChange(p)}
                className={`px-2.5 py-1 rounded transition-colors ${
                  datePreset === p
                    ? 'bg-teal-600 text-white font-semibold shadow-xs'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                {p === 'all'
                  ? 'All Time'
                  : p === 'this_month'
                  ? 'This Month'
                  : p === 'last_month'
                  ? 'Last Month'
                  : p === 'this_year'
                  ? 'This Year'
                  : 'Custom Range'}
              </button>
            ))}

            {datePreset === 'custom' && (
              <div className="flex items-center gap-1.5 ml-2">
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="px-2 py-1 border border-slate-200 rounded text-xs text-slate-800"
                />
                <span className="text-slate-400">to</span>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="px-2 py-1 border border-slate-200 rounded text-xs text-slate-800"
                />
              </div>
            )}
          </div>

          {/* Supplier & Status Filters */}
          <div className="flex items-center gap-2 flex-wrap">
            <input
              type="text"
              placeholder="Filter by supplier..."
              value={vendorFilter}
              onChange={(e) => setVendorFilter(e.target.value)}
              className="px-2.5 py-1 border border-slate-200 rounded text-xs text-slate-800 placeholder-slate-400 w-44"
            />

            {(datePreset !== 'all' || vendorFilter || statusFilter || startDate || endDate) && (
              <button
                onClick={handleResetFilters}
                className="text-xs text-slate-500 hover:text-slate-800 underline font-medium"
              >
                Reset Filters
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Navigation Tabs for Detailed Sections */}
      <div className="flex items-center gap-1 border-b border-slate-200 overflow-x-auto text-xs font-semibold">
        <button
          onClick={() => handleTabChange('invoices')}
          className={`px-4 py-2.5 border-b-2 transition-colors whitespace-nowrap flex items-center gap-1.5 ${
            activeTab === 'invoices'
              ? 'border-teal-600 text-teal-700 bg-teal-50/50'
              : 'border-transparent text-slate-600 hover:text-slate-900'
          }`}
        >
          <FileText className="w-3.5 h-3.5" />
          <span>A. Invoice Report</span>
          <span className="px-1.5 py-0.2 rounded-full bg-slate-100 text-[10px] text-slate-600 font-mono">
            {allInvoices.length}
          </span>
        </button>

        <button
          onClick={() => handleTabChange('verification')}
          className={`px-4 py-2.5 border-b-2 transition-colors whitespace-nowrap flex items-center gap-1.5 ${
            activeTab === 'verification'
              ? 'border-teal-600 text-teal-700 bg-teal-50/50'
              : 'border-transparent text-slate-600 hover:text-slate-900'
          }`}
        >
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>B. Verification Analysis</span>
          {verificationBreakdown.flaggedInvoices.length > 0 && (
            <span className="px-1.5 py-0.2 rounded-full bg-amber-100 text-[10px] text-amber-800 font-mono font-bold">
              {verificationBreakdown.flaggedInvoices.length}
            </span>
          )}
        </button>

        <button
          onClick={() => handleTabChange('mismatches')}
          className={`px-4 py-2.5 border-b-2 transition-colors whitespace-nowrap flex items-center gap-1.5 ${
            activeTab === 'mismatches'
              ? 'border-teal-600 text-teal-700 bg-teal-50/50'
              : 'border-transparent text-slate-600 hover:text-slate-900'
          }`}
        >
          <AlertTriangle className="w-3.5 h-3.5" />
          <span>C. Mismatch Analysis</span>
          <span className="px-1.5 py-0.2 rounded-full bg-slate-100 text-[10px] text-slate-600 font-mono">
            {mismatchRecords.length}
          </span>
        </button>

        <button
          onClick={() => handleTabChange('ledger')}
          className={`px-4 py-2.5 border-b-2 transition-colors whitespace-nowrap flex items-center gap-1.5 ${
            activeTab === 'ledger'
              ? 'border-teal-600 text-teal-700 bg-teal-50/50'
              : 'border-transparent text-slate-600 hover:text-slate-900'
          }`}
        >
          <Scale className="w-3.5 h-3.5" />
          <span>D. Ledger Reconciliation</span>
        </button>

        <button
          onClick={() => handleTabChange('expenses')}
          className={`px-4 py-2.5 border-b-2 transition-colors whitespace-nowrap flex items-center gap-1.5 ${
            activeTab === 'expenses'
              ? 'border-teal-600 text-teal-700 bg-teal-50/50'
              : 'border-transparent text-slate-600 hover:text-slate-900'
          }`}
        >
          <DollarSign className="w-3.5 h-3.5" />
          <span>E. Expenses & Due Dates</span>
        </button>

        <button
          onClick={() => handleTabChange('charts')}
          className={`px-4 py-2.5 border-b-2 transition-colors whitespace-nowrap flex items-center gap-1.5 ${
            activeTab === 'charts'
              ? 'border-teal-600 text-teal-700 bg-teal-50/50'
              : 'border-transparent text-slate-600 hover:text-slate-900'
          }`}
        >
          <BarChart3 className="w-3.5 h-3.5" />
          <span>Visual Trends & Charts</span>
        </button>
      </div>

      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-20 text-slate-500">
          <Loader2 className="w-8 h-8 animate-spin text-teal-600 mb-2" />
          <p className="text-sm font-medium">Calculating reports from database records...</p>
        </div>
      ) : (
        <>
          {/* TAB A: INVOICE REPORT */}
          {activeTab === 'invoices' && (
            <div className="space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-3.5 border border-slate-200 rounded-lg text-xs">
                <div>
                  <h2 className="text-sm font-bold text-slate-900">A. Detailed Invoice Report</h2>
                  <p className="text-slate-500 mt-0.5">
                    Showing {filteredInvoices.length} of {allInvoices.length} recorded invoices.
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <span className="font-medium text-slate-500">Filter Status:</span>
                  <select
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                    className="px-2.5 py-1 bg-slate-50 border border-slate-200 rounded text-slate-700 text-xs cursor-pointer"
                  >
                    <option value="">All Statuses</option>
                    <option value="CONFIRMED">Verified / Confirmed</option>
                    <option value="NEEDS_REVIEW">Needs Review / Flagged</option>
                  </select>
                </div>
              </div>

              {filteredInvoices.length === 0 ? (
                <div className="bg-white border border-slate-200 rounded-lg p-12 text-center text-slate-500 text-xs">
                  No invoices matched your current filter criteria.
                </div>
              ) : (
                <div className="bg-white border border-slate-200 rounded-lg overflow-x-auto shadow-xs">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
                      <tr>
                        <th className="py-3 px-3.5">Invoice #</th>
                        <th className="py-3 px-3">Supplier Name</th>
                        <th className="py-3 px-3">Invoice Date</th>
                        <th className="py-3 px-3">Due Date</th>
                        <th className="py-3 px-3 text-right">Subtotal</th>
                        <th className="py-3 px-3 text-right">Tax</th>
                        <th className="py-3 px-3 text-right">Total Amount</th>
                        <th className="py-3 px-3.5 text-center">Verification Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {filteredInvoices.map((inv) => {
                        const isConfirmed = inv.verification_status === 'CONFIRMED';
                        return (
                          <tr
                            key={inv.id}
                            onClick={() => navigate('/invoices')}
                            className="hover:bg-slate-50/70 transition-colors cursor-pointer"
                          >
                            <td className="py-3 px-3.5 font-semibold text-slate-900 whitespace-nowrap">
                              #{inv.invoice_number}
                            </td>
                            <td className="py-3 px-3 text-slate-700 max-w-[160px] truncate" title={inv.vendor_name}>
                              {inv.vendor_name}
                            </td>
                            <td className="py-3 px-3 text-slate-600 whitespace-nowrap">{inv.invoice_date}</td>
                            <td className="py-3 px-3 text-slate-600 whitespace-nowrap">
                              {inv.due_date || <span className="text-slate-400 italic">Not found</span>}
                            </td>
                            <td className="py-3 px-3 text-right text-slate-600 whitespace-nowrap">
                              {inv.subtotal != null ? formatCurrency(inv.subtotal, inv.currency) : '—'}
                            </td>
                            <td className="py-3 px-3 text-right text-slate-600 whitespace-nowrap">
                              {inv.tax_amount != null ? formatCurrency(inv.tax_amount, inv.currency) : '—'}
                            </td>
                            <td className="py-3 px-3 text-right font-bold text-slate-900 whitespace-nowrap">
                              {formatCurrency(inv.total_amount, inv.currency)}
                            </td>
                            <td className="py-3 px-3.5 text-center whitespace-nowrap">
                              {isConfirmed ? (
                                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-[11px] font-semibold bg-emerald-50 text-emerald-800 border border-emerald-300">
                                  Verified
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-[11px] font-semibold bg-amber-50 text-amber-800 border border-amber-300">
                                  Needs Review
                                </span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* TAB B: VERIFICATION ANALYSIS */}
          {activeTab === 'verification' && (
            <div className="space-y-6">
              {/* Summary Metrics */}
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                <div className="bg-white border border-slate-200 rounded-lg p-3 shadow-xs">
                  <span className="text-[11px] font-medium text-slate-500 block">Total Verified</span>
                  <span className="text-xl font-bold text-emerald-700 mt-1 block">
                    {verificationBreakdown.verifiedCount}
                  </span>
                </div>
                <div className="bg-white border border-slate-200 rounded-lg p-3 shadow-xs">
                  <span className="text-[11px] font-medium text-slate-500 block">Invoices w/ Mismatches</span>
                  <span className="text-xl font-bold text-amber-700 mt-1 block">
                    {verificationBreakdown.mismatchesCount}
                  </span>
                </div>
                <div className="bg-white border border-slate-200 rounded-lg p-3 shadow-xs">
                  <span className="text-[11px] font-medium text-slate-500 block">Requires Review</span>
                  <span className="text-xl font-bold text-slate-800 mt-1 block">
                    {verificationBreakdown.needsReviewCount}
                  </span>
                </div>
                <div className="bg-white border border-slate-200 rounded-lg p-3 shadow-xs">
                  <span className="text-[11px] font-medium text-slate-500 block">Missing Fields</span>
                  <span className="text-xl font-bold text-rose-700 mt-1 block">
                    {verificationBreakdown.missingFieldsCount}
                  </span>
                </div>
                <div className="bg-white border border-slate-200 rounded-lg p-3 shadow-xs">
                  <span className="text-[11px] font-medium text-slate-500 block">Duplicate Warnings</span>
                  <span className="text-xl font-bold text-amber-700 mt-1 block">
                    {verificationBreakdown.duplicateWarningsCount}
                  </span>
                </div>
                <div className="bg-white border border-slate-200 rounded-lg p-3 shadow-xs">
                  <span className="text-[11px] font-medium text-slate-500 block">Calc / Tax Discrepancies</span>
                  <span className="text-xl font-bold text-rose-700 mt-1 block">
                    {verificationBreakdown.calcInconsistenciesCount}
                  </span>
                </div>
              </div>

              {/* Explanatory Flagged Invoices Table */}
              <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-xs">
                <div className="pb-3 border-b border-slate-100 flex items-center justify-between">
                  <div>
                    <h2 className="text-sm font-bold text-slate-900">
                      B. Flagged Invoices & Detection Details
                    </h2>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Specific checks performed by InvoiceIQ extraction and validation engines.
                    </p>
                  </div>
                </div>

                {verificationBreakdown.flaggedInvoices.length === 0 ? (
                  <div className="py-12 text-center text-slate-500 text-xs">
                    <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
                    <p className="font-semibold text-slate-800">All invoices verified cleanly!</p>
                    <p className="text-slate-400 mt-0.5">No calculation, date, or duplicate issues detected.</p>
                  </div>
                ) : (
                  <div className="divide-y divide-slate-100 mt-2">
                    {verificationBreakdown.flaggedInvoices.map((inv) => (
                      <div key={inv.id} className="py-4 space-y-2">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-slate-900">#{inv.invoice_number}</span>
                            <span className="text-slate-500">•</span>
                            <span className="text-slate-700 font-medium">{inv.vendor_name}</span>
                            <span className="text-slate-500">•</span>
                            <span className="font-bold text-slate-900">{formatCurrency(inv.total_amount, inv.currency)}</span>
                          </div>

                          <button
                            onClick={() => navigate('/invoices')}
                            className="inline-flex items-center gap-1 text-xs font-semibold text-teal-600 hover:text-teal-700"
                          >
                            <span>Inspect Invoice</span>
                            <ArrowRight className="w-3 h-3" />
                          </button>
                        </div>

                        {/* Specific Issue Explanations */}
                        <div className="space-y-1.5 pl-2 border-l-2 border-amber-300 bg-amber-50/50 p-2.5 rounded text-xs">
                          {inv.issues.map((iss, idx) => (
                            <div key={idx} className="flex flex-col sm:flex-row sm:items-baseline gap-1.5">
                              <span className="font-semibold text-amber-900 bg-amber-100 px-2 py-0.5 rounded text-[10px] shrink-0">
                                {iss.field} ({iss.type})
                              </span>
                              <span className="text-slate-700 leading-relaxed">
                                {iss.description}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB C: MISMATCH ANALYSIS */}
          {activeTab === 'mismatches' && (
            <div className="space-y-4">
              <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-xs">
                <div className="pb-3 border-b border-slate-100">
                  <h2 className="text-sm font-bold text-slate-900">C. Mismatch Analysis (Ledger vs. Invoices)</h2>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Discrepancies identified between uploaded invoices and uploaded accounting ledgers.
                  </p>
                </div>

                {mismatchRecords.length === 0 ? (
                  <div className="py-12 text-center text-slate-500 text-xs">
                    <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
                    <p className="font-semibold text-slate-800">No active reconciliation discrepancies.</p>
                    <p className="text-slate-400 mt-0.5">
                      Upload an accounting ledger in the Ledger section to cross-verify invoice amounts.
                    </p>
                    <button
                      onClick={() => navigate('/reconciliation')}
                      className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 bg-teal-600 text-white rounded text-xs font-semibold hover:bg-teal-700 transition-colors"
                    >
                      <span>Open Ledger Reconciliation</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ) : (
                  <div className="divide-y divide-slate-100 mt-2">
                    {mismatchRecords.map((item) => (
                      <div key={item.id} className="py-4 space-y-2 text-xs">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-slate-900">{item.record_identifier}</span>
                            <span className="text-slate-400">•</span>
                            <span className="text-slate-700 font-medium">{item.counterparty}</span>
                            <span className="text-slate-400">•</span>
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-50 text-rose-800 border border-rose-200">
                              {item.match_status}
                            </span>
                          </div>

                          <button
                            onClick={() => navigate('/reconciliation')}
                            className="inline-flex items-center gap-1 text-xs font-semibold text-teal-600 hover:text-teal-700"
                          >
                            <span>Resolve Discrepancy</span>
                            <ArrowRight className="w-3 h-3" />
                          </button>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 bg-slate-50 p-2.5 rounded border border-slate-100">
                          <div>
                            <span className="text-slate-400 text-[11px] block">Ledger Expected:</span>
                            <span className="font-semibold text-slate-800">{item.expected_value || '—'}</span>
                          </div>
                          <div>
                            <span className="text-slate-400 text-[11px] block">Invoice Actual:</span>
                            <span className="font-semibold text-slate-800">{item.actual_value || '—'}</span>
                          </div>
                          <div>
                            <span className="text-slate-400 text-[11px] block">Difference Amount:</span>
                            <span className="font-bold text-rose-700">
                              {item.discrepancy_amount ? formatCurrency(item.discrepancy_amount, item.currency) : '—'}
                            </span>
                          </div>
                        </div>

                        {item.evidence_text && (
                          <div className="text-[11px] text-slate-600 bg-amber-50/60 p-2 rounded border border-amber-200 flex items-start gap-1.5">
                            <Info className="w-3.5 h-3.5 text-amber-700 shrink-0 mt-0.5" />
                            <span>{item.evidence_text}</span>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB D: LEDGER RECONCILIATION REPORT */}
          {activeTab === 'ledger' && (
            <div className="space-y-4">
              {/* Summary Stats */}
              <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
                <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-xs">
                  <span className="text-xs font-medium text-slate-500">Matched Records</span>
                  <span className="text-2xl font-bold text-emerald-800 block mt-1">
                    {reconSummary.matched_count}
                  </span>
                  <span className="text-[11px] text-emerald-700">Perfect amount & ID match</span>
                </div>
                <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-xs">
                  <span className="text-xs font-medium text-slate-500">Mismatched Records</span>
                  <span className="text-2xl font-bold text-amber-800 block mt-1">
                    {reconSummary.mismatch_count}
                  </span>
                  <span className="text-[11px] text-amber-700">Discrepancy in totals</span>
                </div>
                <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-xs">
                  <span className="text-xs font-medium text-slate-500">Unmatched Ledger Entries</span>
                  <span className="text-2xl font-bold text-rose-800 block mt-1">
                    {reconSummary.missing_count}
                  </span>
                  <span className="text-[11px] text-rose-700">Missing in invoice store</span>
                </div>
                <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-xs">
                  <span className="text-xs font-medium text-slate-500">Total Compared Rows</span>
                  <span className="text-2xl font-bold text-slate-900 block mt-1">
                    {reconSummary.total_records}
                  </span>
                  <span className="text-[11px] text-slate-500">Across {reconSummary.total_batches} batch(es)</span>
                </div>
              </div>

              {/* Table of items */}
              <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-xs">
                <div className="pb-3 border-b border-slate-100 flex items-center justify-between">
                  <div>
                    <h2 className="text-sm font-bold text-slate-900">
                      D. Ledger Reconciliation Records
                    </h2>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Detailed matching status across internal accounting lines.
                    </p>
                  </div>
                  <button
                    onClick={() => navigate('/reconciliation')}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-teal-600 text-white rounded text-xs font-semibold hover:bg-teal-700 transition-colors shadow-xs"
                  >
                    <span>Open Full Reconciliation</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>

                {reconciliationItems.length === 0 ? (
                  <div className="py-12 text-center text-slate-500 text-xs">
                    No reconciliation items loaded. Upload a ledger CSV or XLSX in the Ledger section.
                  </div>
                ) : (
                  <div className="overflow-x-auto mt-2">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
                        <tr>
                          <th className="py-3 px-3">Batch</th>
                          <th className="py-3 px-3">Identifier</th>
                          <th className="py-3 px-3">Counterparty</th>
                          <th className="py-3 px-3">Date</th>
                          <th className="py-3 px-3 text-right">Expected</th>
                          <th className="py-3 px-3 text-right">Actual</th>
                          <th className="py-3 px-3 text-right">Difference</th>
                          <th className="py-3 px-3 text-center">Reconciliation Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {reconciliationItems.map((item) => {
                          const isMatch = item.match_status === 'MATCH' || item.match_status === 'MATCHED';
                          return (
                            <tr key={item.id} className="hover:bg-slate-50/70">
                              <td className="py-2.5 px-3 text-slate-600 max-w-[120px] truncate">
                                {item.batch_title}
                              </td>
                              <td className="py-2.5 px-3 font-semibold text-slate-900">
                                {item.record_identifier}
                              </td>
                              <td className="py-2.5 px-3 text-slate-700">{item.counterparty}</td>
                              <td className="py-2.5 px-3 text-slate-600">{item.transaction_date || '—'}</td>
                              <td className="py-2.5 px-3 text-right text-slate-700">{item.expected_value || '—'}</td>
                              <td className="py-2.5 px-3 text-right text-slate-700">{item.actual_value || '—'}</td>
                              <td className="py-2.5 px-3 text-right font-medium text-slate-900">
                                {item.discrepancy_amount ? formatCurrency(item.discrepancy_amount, item.currency) : '—'}
                              </td>
                              <td className="py-2.5 px-3 text-center">
                                <span
                                  className={`inline-flex px-2 py-0.5 rounded text-[11px] font-semibold border ${
                                    isMatch
                                      ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                                      : 'bg-rose-50 text-rose-800 border-rose-200'
                                  }`}
                                >
                                  {item.match_status}
                                </span>
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

          {/* TAB E: EXPENSES AND DUE DATES */}
          {activeTab === 'expenses' && (
            <div className="space-y-4">
              <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-xs">
                <div className="pb-3 border-b border-slate-100 flex items-center justify-between">
                  <div>
                    <h2 className="text-sm font-bold text-slate-900">
                      E. Expenses and Due Dates Overview
                    </h2>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Financial summary of invoice-wise expenses, dates, and upcoming deadlines.
                    </p>
                  </div>
                  <div className="text-right">
                    <span className="text-xs text-slate-400 block">Total Invoiced Expenses</span>
                    <span className="text-lg font-bold text-slate-900">
                      {formatCurrency(summary.total_invoiced_amount, summary.currency)}
                    </span>
                  </div>
                </div>

                {allInvoices.length === 0 ? (
                  <div className="py-12 text-center text-slate-500 text-xs">
                    No invoice expense records found.
                  </div>
                ) : (
                  <div className="overflow-x-auto mt-2">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
                        <tr>
                          <th className="py-3 px-3">Invoice Number</th>
                          <th className="py-3 px-3">Supplier Name</th>
                          <th className="py-3 px-3">Invoice Date</th>
                          <th className="py-3 px-3">Due Date</th>
                          <th className="py-3 px-3 text-right">Invoice Expense Amount</th>
                          <th className="py-3 px-3 text-center">Deadline Alert</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {allInvoices.map((inv) => {
                          const reminder = getDueDateReminder(inv.due_date);
                          return (
                            <tr
                              key={inv.id}
                              onClick={() => navigate('/invoices')}
                              className="hover:bg-slate-50/70 cursor-pointer"
                            >
                              <td className="py-2.5 px-3 font-semibold text-slate-900 whitespace-nowrap">
                                #{inv.invoice_number}
                              </td>
                              <td className="py-2.5 px-3 text-slate-700">{inv.vendor_name}</td>
                              <td className="py-2.5 px-3 text-slate-600 whitespace-nowrap">{inv.invoice_date}</td>
                              <td className="py-2.5 px-3 text-slate-600 whitespace-nowrap">
                                {inv.due_date || 'No due date'}
                              </td>
                              <td className="py-2.5 px-3 text-right font-bold text-slate-900 whitespace-nowrap">
                                {formatCurrency(inv.total_amount, inv.currency)}
                              </td>
                              <td className="py-2.5 px-3 text-center whitespace-nowrap">
                                <span
                                  className={`inline-flex px-2 py-0.5 rounded text-[11px] font-semibold border ${reminder.badgeClass}`}
                                >
                                  {reminder.text}
                                </span>
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

          {/* TAB: USEFUL CHARTS & TRENDS (Section 3) */}
          {activeTab === 'charts' && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Chart 1: Monthly Invoice Expenses Over Time */}
                <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-xs flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                      <div>
                        <h3 className="text-sm font-bold text-slate-900">
                          Invoice Expenses Over Time
                        </h3>
                        <p className="text-xs text-slate-500">Monthly invoiced totals</p>
                      </div>
                      <div className="w-3 h-3 bg-teal-600 rounded-xs" />
                    </div>

                    {monthlyTrends.length === 0 ? (
                      <div className="py-16 text-center text-slate-400 text-xs">
                        No monthly expense records available.
                      </div>
                    ) : (
                      <div className="pt-6 pb-2">
                        {(() => {
                          const maxVal = Math.max(
                            ...monthlyTrends.map((m) => parseFloat(m.invoiced_amount || 0)),
                            1
                          );
                          return (
                            <div className="grid grid-cols-6 gap-2 sm:gap-4 items-end h-40 border-b border-slate-100 pb-2">
                              {monthlyTrends.map((m) => {
                                const val = parseFloat(m.invoiced_amount || 0);
                                const heightPercent = Math.max(6, Math.round((val / maxVal) * 100));
                                return (
                                  <div key={m.month_key} className="flex flex-col items-center h-full justify-end">
                                    <div className="relative group w-full flex justify-center">
                                      <div
                                        className="w-5 sm:w-8 bg-teal-600 hover:bg-teal-700 rounded-t transition-all"
                                        style={{ height: `${heightPercent}%` }}
                                      />
                                      <div className="absolute bottom-full mb-1 hidden group-hover:block z-10 px-2 py-1 bg-slate-900 text-white text-[10px] rounded whitespace-nowrap shadow-md">
                                        {formatCurrency(val, summary.currency)} ({m.invoiced_count} inv)
                                      </div>
                                    </div>
                                    <span className="text-[10px] text-slate-500 mt-2 truncate w-full text-center">
                                      {m.month_label}
                                    </span>
                                  </div>
                                );
                              })}
                            </div>
                          );
                        })()}
                      </div>
                    )}
                  </div>
                  <p className="text-[11px] text-slate-400 mt-3">Source: Validated invoice database</p>
                </div>

                {/* Chart 2: Ledger Comparison (Matched vs Mismatched vs Unmatched) */}
                <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-xs flex flex-col justify-between">
                  <div>
                    <div className="pb-3 border-b border-slate-100">
                      <h3 className="text-sm font-bold text-slate-900">
                        Reconciliation Status Distribution
                      </h3>
                      <p className="text-xs text-slate-500">Comparison across ledger entries</p>
                    </div>

                    {reconSummary.total_records === 0 ? (
                      <div className="py-16 text-center text-slate-400 text-xs">
                        No reconciliation batches executed yet.
                      </div>
                    ) : (
                      <div className="space-y-4 pt-6">
                        {/* Segmented Bar */}
                        <div className="h-4 w-full bg-slate-100 rounded-full overflow-hidden flex shadow-inner">
                          {reconSummary.matched_count > 0 && (
                            <div
                              style={{
                                width: `${(reconSummary.matched_count / reconSummary.total_records) * 100}%`,
                              }}
                              className="bg-emerald-600 transition-all"
                              title={`Matched: ${reconSummary.matched_count}`}
                            />
                          )}
                          {reconSummary.mismatch_count > 0 && (
                            <div
                              style={{
                                width: `${(reconSummary.mismatch_count / reconSummary.total_records) * 100}%`,
                              }}
                              className="bg-amber-500 transition-all"
                              title={`Mismatched: ${reconSummary.mismatch_count}`}
                            />
                          )}
                          {reconSummary.missing_count > 0 && (
                            <div
                              style={{
                                width: `${(reconSummary.missing_count / reconSummary.total_records) * 100}%`,
                              }}
                              className="bg-rose-500 transition-all"
                              title={`Missing: ${reconSummary.missing_count}`}
                            />
                          )}
                        </div>

                        {/* Legend */}
                        <div className="grid grid-cols-3 gap-2 pt-4 text-xs">
                          <div className="p-2.5 bg-emerald-50 rounded border border-emerald-100">
                            <span className="font-semibold text-emerald-800 block">Matched</span>
                            <span className="text-base font-bold text-emerald-900">
                              {reconSummary.matched_count}
                            </span>
                          </div>
                          <div className="p-2.5 bg-amber-50 rounded border border-amber-100">
                            <span className="font-semibold text-amber-800 block">Mismatched</span>
                            <span className="text-base font-bold text-amber-900">
                              {reconSummary.mismatch_count}
                            </span>
                          </div>
                          <div className="p-2.5 bg-rose-50 rounded border border-rose-100">
                            <span className="font-semibold text-rose-800 block">Unmatched</span>
                            <span className="text-base font-bold text-rose-900">
                              {reconSummary.missing_count}
                            </span>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                  <p className="text-[11px] text-slate-400 mt-3">Source: Accounting Ledger Comparison</p>
                </div>
              </div>

              {/* Chart 3: Verification Integrity Breakdown */}
              <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-xs">
                <div className="pb-3 border-b border-slate-100">
                  <h3 className="text-sm font-bold text-slate-900">
                    Invoice Verification Outcomes
                  </h3>
                  <p className="text-xs text-slate-500">
                    Proportion of verified invoices vs invoices requiring review
                  </p>
                </div>

                {allInvoices.length === 0 ? (
                  <div className="py-10 text-center text-slate-400 text-xs">
                    No invoices recorded.
                  </div>
                ) : (
                  <div className="pt-4 space-y-3">
                    <div className="h-4 w-full bg-slate-100 rounded-full overflow-hidden flex shadow-inner">
                      <div
                        style={{
                          width: `${(verificationBreakdown.verifiedCount / allInvoices.length) * 100}%`,
                        }}
                        className="bg-teal-600"
                        title={`Verified: ${verificationBreakdown.verifiedCount}`}
                      />
                      <div
                        style={{
                          width: `${(verificationBreakdown.needsReviewCount / allInvoices.length) * 100}%`,
                        }}
                        className="bg-amber-500"
                        title={`Needs Review: ${verificationBreakdown.needsReviewCount}`}
                      />
                    </div>

                    <div className="flex items-center justify-between text-xs pt-1">
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 bg-teal-600 rounded-xs" />
                        <span className="font-semibold text-slate-800">
                          Verified Integrity ({verificationBreakdown.verifiedCount} / {allInvoices.length})
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 bg-amber-500 rounded-xs" />
                        <span className="font-semibold text-slate-800">
                          Needs Review ({verificationBreakdown.needsReviewCount} / {allInvoices.length})
                        </span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
