import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  FileText,
  AlertCircle,
  AlertTriangle,
  Calendar,
  Clock,
  Sparkles,
  ArrowRight,
  Loader2,
  CheckCircle2,
  Building,
  Upload,
  Scale,
  DollarSign,
  FileCheck,
  ShieldCheck,
  BarChart3,
  Download,
  Filter,
  X,
  RefreshCw,
  FileDown,
  Layers,
  ChevronRight,
  Eye,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import {
  getDashboardAnalytics,
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

export default function OverviewReports() {
  const { user } = useAuth();
  const navigate = useNavigate();

  // Primary live overview metrics
  const [data, setData] = useState(null);
  const [selectedCurrency, setSelectedCurrency] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState('');

  // Report Modal states
  const [activeReportModal, setActiveReportModal] = useState(null); // 'invoice' | 'verification' | 'ledger' | null
  const [modalReportsData, setModalReportsData] = useState(null);
  const [isModalLoading, setIsModalLoading] = useState(false);
  const [modalError, setModalError] = useState('');
  const [modalSuccess, setModalSuccess] = useState('');
  const [downloadingType, setDownloadingType] = useState(null);

  // Modal Filters
  const [datePreset, setDatePreset] = useState('all');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [vendorFilter, setVendorFilter] = useState('');

  // Fetch live dashboard metrics
  const fetchOverview = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage('');
    try {
      const res = await getDashboardAnalytics();
      setData(res);
      if (res.currency && !selectedCurrency) {
        setSelectedCurrency(res.currency);
      }
    } catch (err) {
      setErrorMessage(err.message || 'Failed to load overview analytics.');
    } finally {
      setIsLoading(false);
    }
  }, [selectedCurrency]);

  useEffect(() => {
    fetchOverview();
  }, [fetchOverview]);

  // Handle Preset Change for Report Modal
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

  // Fetch report data when modal opens or filters change
  const fetchModalData = useCallback(async () => {
    if (!activeReportModal) return;
    if (startDate && endDate && startDate > endDate) {
      setModalError('Start date cannot be after end date.');
      return;
    }

    setIsModalLoading(true);
    setModalError('');
    try {
      const res = await getReportsAnalytics({
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        vendor: vendorFilter.trim() || undefined,
      });
      setModalReportsData(res);
    } catch (err) {
      setModalError(err.message || 'Failed to load report details.');
    } finally {
      setIsModalLoading(false);
    }
  }, [activeReportModal, startDate, endDate, vendorFilter]);

  useEffect(() => {
    if (activeReportModal) {
      fetchModalData();
    }
  }, [activeReportModal, fetchModalData]);

  // Open a specific report modal
  const openReportModal = (type) => {
    setActiveReportModal(type);
    setDatePreset('all');
    setStartDate('');
    setEndDate('');
    setVendorFilter('');
    setModalError('');
    setModalSuccess('');
  };

  // Handle report downloads inside modal
  const handleDownload = async (type) => {
    setDownloadingType(type);
    setModalError('');
    setModalSuccess('');
    try {
      const params = {
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        vendor: vendorFilter.trim() || undefined,
      };

      if (type === 'pdf') {
        await downloadReportPdf(params);
        setModalSuccess('Executive summary PDF report generated and downloaded.');
      } else if (type === 'invoices') {
        await downloadInvoicesCsv(params);
        setModalSuccess('Invoices CSV report exported successfully.');
      } else if (type === 'reconciliation') {
        await downloadReconciliationCsv(params);
        setModalSuccess('Ledger reconciliation CSV exported successfully.');
      }
      setTimeout(() => setModalSuccess(''), 4000);
    } catch (err) {
      setModalError(err.message || `Failed to export ${type.toUpperCase()}.`);
    } finally {
      setDownloadingType(null);
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] text-slate-500">
        <Loader2 className="w-8 h-8 animate-spin text-teal-600 mb-2" />
        <p className="text-sm font-medium">Loading live overview and verification metrics...</p>
      </div>
    );
  }

  if (errorMessage) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm flex items-center gap-2">
        <AlertCircle className="w-5 h-5 shrink-0 text-red-600" />
        <span>{errorMessage}</span>
      </div>
    );
  }

  const activeCurrency = selectedCurrency || data?.currency || 'USD';
  const activeCurrencyData =
    data?.has_multiple_currencies && data?.by_currency?.[activeCurrency]
      ? data.by_currency[activeCurrency]
      : data || {};

  // Metrics
  const total_invoiced_amount = activeCurrencyData.total_invoiced_amount ?? (data?.total_invoiced_amount || '0.00');
  const total_invoices_count = activeCurrencyData.total_invoices_count ?? (data?.total_invoices_count || 0);
  const mismatches_count = data?.mismatches_count ?? 0;
  const upcoming_due_dates_count = data?.upcoming_due_dates_count ?? (data?.due_within_7_days_count || 0);

  const verified_count = data?.verified_invoices_count ?? Math.max(0, total_invoices_count - (data?.needs_review_count || 0));
  const needs_review_count = data?.needs_review_count ?? 0;
  const recent_invoices = data?.recent_invoices || [];

  // Reconciliation Summary from batch data
  const reconSummary = data?.reconciliation_summary || {
    matched_count: 0,
    mismatch_count: 0,
    missing_count: 0,
    total_records: 0,
  };

  return (
    <div className="space-y-8 pb-10">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Overview & Reports</h1>
          <p className="text-sm text-slate-500 mt-1">
            Invoice verification, mismatch detection, and ledger reconciliation center.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => navigate('/invoices')}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-md text-xs font-medium transition-colors shadow-xs"
          >
            <Upload className="w-3.5 h-3.5" />
            <span>Upload Invoice</span>
          </button>
          <button
            onClick={() => navigate('/reconciliation')}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 rounded-md text-xs font-medium transition-colors shadow-xs"
          >
            <Scale className="w-3.5 h-3.5 text-teal-600" />
            <span>Reconcile Ledger</span>
          </button>
        </div>
      </div>

      {/* Multi-currency Switcher Banner (if multiple currencies exist) */}
      {data?.has_multiple_currencies && data?.by_currency && Object.keys(data.by_currency).length > 1 && (
        <div className="bg-amber-50/90 border border-amber-200 rounded-lg p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-amber-950 shadow-xs">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-amber-900">Multi-Currency Invoices:</span>
            <span>Expenses are segregated by currency to ensure financial integrity.</span>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            <span className="text-amber-800 font-medium">Currency:</span>
            {Object.keys(data.by_currency).map((curr) => (
              <button
                key={curr}
                type="button"
                onClick={() => setSelectedCurrency(curr)}
                className={`px-2.5 py-1 rounded text-xs font-semibold transition-colors ${
                  activeCurrency === curr
                    ? 'bg-amber-800 text-white shadow-xs'
                    : 'bg-white text-amber-800 hover:bg-amber-100 border border-amber-300'
                }`}
              >
                {curr}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* SECTION 1 — Overview (4 KPI Cards) */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-bold text-slate-500 uppercase tracking-wider">
            Section 1 — Overview
          </h2>
          <span className="text-xs text-slate-400">Live Database Totals</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Card 1: Total Invoice Expenses */}
          <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-xs hover:border-slate-300 transition-colors">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-500">Total Invoice Expenses</span>
              <div className="w-8 h-8 rounded-full bg-teal-50 text-teal-700 flex items-center justify-center">
                <DollarSign className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-2.5">
              <span className="text-2xl font-bold text-slate-900">
                {formatCurrency(total_invoiced_amount, activeCurrency)}
              </span>
            </div>
            <p className="mt-1 text-xs text-slate-500">
              From {total_invoices_count} valid invoice{total_invoices_count === 1 ? '' : 's'}
            </p>
          </div>

          {/* Card 2: Invoices Processed */}
          <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-xs hover:border-slate-300 transition-colors">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-500">Invoices Processed</span>
              <div className="w-8 h-8 rounded-full bg-slate-100 text-slate-700 flex items-center justify-center">
                <FileCheck className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-2.5">
              <span className="text-2xl font-bold text-slate-900">{total_invoices_count}</span>
            </div>
            <p className="mt-1 text-xs text-slate-500">Uploaded and processed</p>
          </div>

          {/* Card 3: Verification Summary */}
          <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-xs hover:border-slate-300 transition-colors">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-500">Verification Summary</span>
              <div className="w-8 h-8 rounded-full bg-emerald-50 text-emerald-700 flex items-center justify-center">
                <ShieldCheck className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-2.5 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-emerald-700">{verified_count}</span>
              <span className="text-xs font-semibold text-slate-700">Verified</span>
              <span className="text-slate-300">•</span>
              <span className="text-base font-bold text-amber-600">{needs_review_count}</span>
              <span className="text-xs font-semibold text-slate-500">Pending</span>
            </div>
            <p className="mt-1 text-xs text-slate-500">Based on data integrity checks</p>
          </div>

          {/* Card 4: Upcoming Due Dates (Reminder only, zero payment inference) */}
          <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-xs hover:border-slate-300 transition-colors">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-500">Upcoming Due Dates</span>
              <div className="w-8 h-8 rounded-full bg-sky-50 text-sky-700 flex items-center justify-center">
                <Clock className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-2.5 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-sky-800">{upcoming_due_dates_count}</span>
              <span className="text-xs font-semibold text-slate-600">Due Soon</span>
            </div>
            <p className="mt-1 text-xs text-slate-500">Invoices requiring deadline attention</p>
          </div>
        </div>
      </section>

      {/* SECTION 2 — Verification Analysis (Most important section) */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-xs font-bold text-slate-500 uppercase tracking-wider">
              Section 2 — Verification Analysis
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Click any card to inspect filtered invoices directly.
            </p>
          </div>
          <span className="text-xs text-teal-600 font-medium hidden sm:inline">
            Interactive Filters &rarr;
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Card 1: Verified */}
          <div
            onClick={() => navigate('/invoices?status=CONFIRMED')}
            className="group bg-white border border-emerald-200 hover:border-emerald-400 hover:shadow-md rounded-lg p-5 cursor-pointer transition-all duration-150"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-10 h-10 rounded-lg bg-emerald-100 text-emerald-800 flex items-center justify-center shrink-0">
                  <CheckCircle2 className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900 group-hover:text-emerald-800 transition-colors">
                    Verified
                  </h3>
                  <p className="text-xs text-slate-500">Integrity confirmed</p>
                </div>
              </div>
              <ChevronRight className="w-4 h-4 text-slate-400 group-hover:text-emerald-700 group-hover:translate-x-0.5 transition-all" />
            </div>

            <div className="mt-4 flex items-baseline justify-between">
              <span className="text-3xl font-extrabold text-emerald-800">{verified_count}</span>
              <span className="text-xs font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                View verified &rarr;
              </span>
            </div>
            <p className="mt-2 text-xs text-slate-500">
              Invoices passing arithmetic, GSTIN/tax consistency, and duplicate checks.
            </p>
          </div>

          {/* Card 2: Mismatch Found */}
          <div
            onClick={() => navigate('/invoices?status=MISMATCH')}
            className="group bg-white border border-amber-200 hover:border-amber-400 hover:shadow-md rounded-lg p-5 cursor-pointer transition-all duration-150"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-10 h-10 rounded-lg bg-amber-100 text-amber-800 flex items-center justify-center shrink-0">
                  <AlertTriangle className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900 group-hover:text-amber-800 transition-colors">
                    Mismatch Found
                  </h3>
                  <p className="text-xs text-slate-500">Discrepancies flagged</p>
                </div>
              </div>
              <ChevronRight className="w-4 h-4 text-slate-400 group-hover:text-amber-700 group-hover:translate-x-0.5 transition-all" />
            </div>

            <div className="mt-4 flex items-baseline justify-between">
              <span className="text-3xl font-extrabold text-amber-800">{mismatches_count}</span>
              <span className="text-xs font-medium text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                View mismatches &rarr;
              </span>
            </div>
            <p className="mt-2 text-xs text-slate-500">
              Invoices with calculation issues, ledger discrepancies, or ML anomalies.
            </p>
          </div>

          {/* Card 3: Needs Review */}
          <div
            onClick={() => navigate('/invoices?status=NEEDS_REVIEW')}
            className="group bg-white border border-slate-200 hover:border-slate-400 hover:shadow-md rounded-lg p-5 cursor-pointer transition-all duration-150"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-10 h-10 rounded-lg bg-slate-100 text-slate-700 flex items-center justify-center shrink-0">
                  <AlertCircle className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900 group-hover:text-slate-800 transition-colors">
                    Needs Review
                  </h3>
                  <p className="text-xs text-slate-500">Manual review required</p>
                </div>
              </div>
              <ChevronRight className="w-4 h-4 text-slate-400 group-hover:text-slate-700 group-hover:translate-x-0.5 transition-all" />
            </div>

            <div className="mt-4 flex items-baseline justify-between">
              <span className="text-3xl font-extrabold text-slate-800">{needs_review_count}</span>
              <span className="text-xs font-medium text-slate-700 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
                View pending &rarr;
              </span>
            </div>
            <p className="mt-2 text-xs text-slate-500">
              Invoices flagged with missing fields, arithmetic variances, or dates.
            </p>
          </div>
        </div>
      </section>

      {/* SECTION 3 — Ledger Reconciliation Summary */}
      <section className="bg-white border border-slate-200 rounded-lg p-5 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-100">
          <div>
            <div className="flex items-center gap-2">
              <Scale className="w-4 h-4 text-teal-600" />
              <h2 className="text-sm font-bold text-slate-900">
                Section 3 — Ledger Reconciliation Summary
              </h2>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Comparison of uploaded invoices against internal accounting ledger entries.
            </p>
          </div>

          <button
            onClick={() => navigate('/reconciliation')}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-teal-600 hover:bg-teal-700 text-white rounded text-xs font-medium transition-colors shadow-xs shrink-0"
          >
            <span>View Details</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-4">
          <div className="p-3.5 bg-emerald-50/70 border border-emerald-100 rounded-md">
            <span className="text-xs font-medium text-emerald-800 block">Matched Records</span>
            <span className="text-2xl font-bold text-emerald-900 mt-1 block">
              {reconSummary.matched_count}
            </span>
            <span className="text-[11px] text-emerald-700 mt-0.5 block">
              Amounts and identifiers match exactly
            </span>
          </div>

          <div className="p-3.5 bg-amber-50/70 border border-amber-100 rounded-md">
            <span className="text-xs font-medium text-amber-800 block">Mismatched Records</span>
            <span className="text-2xl font-bold text-amber-900 mt-1 block">
              {reconSummary.mismatch_count}
            </span>
            <span className="text-[11px] text-amber-700 mt-0.5 block">
              Discrepancies in total or posting dates
            </span>
          </div>

          <div className="p-3.5 bg-rose-50/70 border border-rose-100 rounded-md">
            <span className="text-xs font-medium text-rose-800 block">Missing Ledger Entries</span>
            <span className="text-2xl font-bold text-rose-900 mt-1 block">
              {reconSummary.missing_count}
            </span>
            <span className="text-[11px] text-rose-700 mt-0.5 block">
              Unmatched records requiring entry
            </span>
          </div>
        </div>
      </section>

      {/* 2-COLUMN LAYOUT: SECTION 4 (Recent Activity) & SECTION 5 (Due Date Reminder) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* SECTION 4 — Recent Activity (Latest 5 Invoices) */}
        <section className="bg-white border border-slate-200 rounded-lg p-5 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div>
                <h2 className="text-sm font-bold text-slate-900">Section 4 — Recent Activity</h2>
                <p className="text-xs text-slate-500">Latest 5 processed invoices</p>
              </div>
              <Link
                to="/invoices"
                className="text-xs font-semibold text-teal-600 hover:text-teal-700 inline-flex items-center gap-1"
              >
                <span>View all</span>
                <ArrowRight className="w-3 h-3" />
              </Link>
            </div>

            {recent_invoices.length === 0 ? (
              <div className="py-10 text-center text-slate-500">
                <FileText className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                <p className="text-xs">No invoices uploaded yet.</p>
                <button
                  onClick={() => navigate('/invoices')}
                  className="mt-2 text-xs text-teal-600 font-semibold hover:underline"
                >
                  Upload your first invoice
                </button>
              </div>
            ) : (
              <div className="divide-y divide-slate-100 overflow-x-auto">
                <table className="w-full text-left text-xs mt-2">
                  <thead>
                    <tr className="text-slate-400 font-medium">
                      <th className="py-2 pr-2">Invoice #</th>
                      <th className="py-2 px-2">Supplier</th>
                      <th className="py-2 px-2 text-right">Amount</th>
                      <th className="py-2 px-2">Due Date</th>
                      <th className="py-2 pl-2 text-center">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {recent_invoices.slice(0, 5).map((inv) => {
                      const isNeedsReview = inv.verification_status === 'NEEDS_REVIEW';
                      return (
                        <tr
                          key={inv.id}
                          className="hover:bg-slate-50/80 transition-colors cursor-pointer"
                          onClick={() => navigate('/invoices')}
                        >
                          <td className="py-2.5 pr-2 font-semibold text-slate-900 whitespace-nowrap">
                            #{inv.invoice_number}
                          </td>
                          <td className="py-2.5 px-2 text-slate-700 max-w-[120px] truncate" title={inv.vendor_name}>
                            {inv.vendor_name}
                          </td>
                          <td className="py-2.5 px-2 text-right font-medium text-slate-900 whitespace-nowrap">
                            {formatCurrency(inv.total_amount, inv.currency)}
                          </td>
                          <td className="py-2.5 px-2 text-slate-500 whitespace-nowrap">
                            {inv.due_date || 'N/A'}
                          </td>
                          <td className="py-2.5 pl-2 text-center whitespace-nowrap">
                            {isNeedsReview ? (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-50 text-amber-800 border border-amber-300">
                                Needs Review
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-50 text-emerald-800 border border-emerald-300">
                                Verified
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
        </section>

        {/* SECTION 5 — Due Date Reminder (Reminder only, zero payment inference) */}
        <section className="bg-white border border-slate-200 rounded-lg p-5 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div>
                <h2 className="text-sm font-bold text-slate-900">Section 5 — Due Date Reminder</h2>
                <p className="text-xs text-slate-500">Upcoming and passed deadline alerts</p>
              </div>
              <span className="text-[11px] text-slate-400 bg-slate-100 px-2 py-0.5 rounded">
                Reminder Only
              </span>
            </div>

            {recent_invoices.length === 0 ? (
              <div className="py-10 text-center text-slate-500">
                <Clock className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                <p className="text-xs">No invoice deadlines recorded yet.</p>
              </div>
            ) : (
              <div className="divide-y divide-slate-100 mt-2 space-y-1">
                {recent_invoices.slice(0, 5).map((inv) => {
                  const reminder = getDueDateReminder(inv.due_date);
                  return (
                    <div
                      key={inv.id}
                      className="py-2.5 flex items-center justify-between gap-3 text-xs"
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-slate-900 truncate">
                            {inv.vendor_name}
                          </span>
                          <span className="text-slate-400 font-mono text-[11px]">
                            #{inv.invoice_number}
                          </span>
                        </div>
                        <div className="text-[11px] text-slate-500 mt-0.5 flex items-center gap-2">
                          <span>Due: {inv.due_date || 'No date recorded'}</span>
                          <span>•</span>
                          <span>{formatCurrency(inv.total_amount, inv.currency)}</span>
                        </div>
                      </div>

                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold border shrink-0 ${reminder.badgeClass}`}
                      >
                        {reminder.text}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </section>
      </div>

      {/* SECTION 6 — Detailed Reports */}
      <section>
        <div className="mb-3">
          <h2 className="text-xs font-bold text-slate-500 uppercase tracking-wider">
            Section 6 — Detailed Reports
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Focused report centers with modal viewing and instant CSV / PDF exports.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Card 1: Invoice Report */}
          <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-xs flex flex-col justify-between hover:border-slate-300 transition-colors">
            <div>
              <div className="w-9 h-9 rounded bg-teal-50 text-teal-700 flex items-center justify-center mb-3">
                <FileText className="w-5 h-5" />
              </div>
              <h3 className="text-sm font-bold text-slate-900">Invoice Report</h3>
              <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                Comprehensive extracted invoice records, line item totals, tax breakdown, and issue notes.
              </p>
            </div>
            <div className="mt-5 pt-3 border-t border-slate-100 flex items-center justify-between">
              <span className="text-xs text-slate-400 font-medium">CSV & PDF Available</span>
              <button
                onClick={() => openReportModal('invoice')}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 text-white rounded text-xs font-medium transition-colors shadow-xs"
              >
                <span>View Report</span>
                <ArrowRight className="w-3 h-3" />
              </button>
            </div>
          </div>

          {/* Card 2: Verification Report */}
          <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-xs flex flex-col justify-between hover:border-slate-300 transition-colors">
            <div>
              <div className="w-9 h-9 rounded bg-amber-50 text-amber-700 flex items-center justify-center mb-3">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <h3 className="text-sm font-bold text-slate-900">Verification Report</h3>
              <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                Audit trail of arithmetic mismatches, missing required fields, duplicates, and ML screening flags.
              </p>
            </div>
            <div className="mt-5 pt-3 border-t border-slate-100 flex items-center justify-between">
              <span className="text-xs text-slate-400 font-medium">Anomaly & Audit</span>
              <button
                onClick={() => openReportModal('verification')}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 text-white rounded text-xs font-medium transition-colors shadow-xs"
              >
                <span>View Report</span>
                <ArrowRight className="w-3 h-3" />
              </button>
            </div>
          </div>

          {/* Card 3: Ledger Report */}
          <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-xs flex flex-col justify-between hover:border-slate-300 transition-colors">
            <div>
              <div className="w-9 h-9 rounded bg-teal-50 text-teal-700 flex items-center justify-center mb-3">
                <Scale className="w-5 h-5" />
              </div>
              <h3 className="text-sm font-bold text-slate-900">Ledger Report</h3>
              <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                Detailed reconciliation comparison records showing matched items, amount differences, and missing entries.
              </p>
            </div>
            <div className="mt-5 pt-3 border-t border-slate-100 flex items-center justify-between">
              <span className="text-xs text-slate-400 font-medium">Reconciliation CSV</span>
              <button
                onClick={() => openReportModal('ledger')}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 text-white rounded text-xs font-medium transition-colors shadow-xs"
              >
                <span>View Report</span>
                <ArrowRight className="w-3 h-3" />
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* FOCUSED REPORT MODAL */}
      {activeReportModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4 overflow-y-auto">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 w-full max-w-5xl max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in-50 duration-200">
            {/* Modal Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50/50">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded bg-teal-600 text-white flex items-center justify-center font-bold text-sm">
                  {activeReportModal === 'invoice' && <FileText className="w-4 h-4" />}
                  {activeReportModal === 'verification' && <ShieldCheck className="w-4 h-4" />}
                  {activeReportModal === 'ledger' && <Scale className="w-4 h-4" />}
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-900">
                    {activeReportModal === 'invoice' && 'Invoice Report'}
                    {activeReportModal === 'verification' && 'Verification & Anomaly Report'}
                    {activeReportModal === 'ledger' && 'Ledger Reconciliation Report'}
                  </h3>
                  <p className="text-xs text-slate-500">
                    Filter records, inspect details, and export cleanly.
                  </p>
                </div>
              </div>

              <button
                onClick={() => setActiveReportModal(null)}
                className="p-1.5 text-slate-400 hover:text-slate-600 rounded-md hover:bg-slate-100 transition-colors"
                title="Close"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Filter Toolbar inside Modal */}
            <div className="px-6 py-3 border-b border-slate-200 bg-white flex flex-wrap items-center justify-between gap-3 text-xs">
              {/* Presets & Dates */}
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-semibold text-slate-600">Period:</span>
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
                      ? 'All'
                      : p === 'this_month'
                      ? 'This Month'
                      : p === 'last_month'
                      ? 'Last Month'
                      : p === 'this_year'
                      ? 'This Year'
                      : 'Custom'}
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

              {/* Export Buttons */}
              <div className="flex items-center gap-2">
                {activeReportModal === 'invoice' && (
                  <>
                    <button
                      onClick={() => handleDownload('invoices')}
                      disabled={downloadingType === 'invoices'}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 rounded text-xs font-medium transition-colors shadow-xs disabled:opacity-50"
                    >
                      {downloadingType === 'invoices' ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Download className="w-3.5 h-3.5" />
                      )}
                      <span>Export CSV</span>
                    </button>
                    <button
                      onClick={() => handleDownload('pdf')}
                      disabled={downloadingType === 'pdf'}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-teal-600 hover:bg-teal-700 text-white rounded text-xs font-medium transition-colors shadow-xs disabled:opacity-50"
                    >
                      {downloadingType === 'pdf' ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <FileDown className="w-3.5 h-3.5" />
                      )}
                      <span>Export PDF</span>
                    </button>
                  </>
                )}

                {activeReportModal === 'verification' && (
                  <>
                    <button
                      onClick={() => handleDownload('invoices')}
                      disabled={downloadingType === 'invoices'}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 rounded text-xs font-medium transition-colors shadow-xs disabled:opacity-50"
                    >
                      {downloadingType === 'invoices' ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Download className="w-3.5 h-3.5" />
                      )}
                      <span>Export Verification CSV</span>
                    </button>
                    <button
                      onClick={() => handleDownload('pdf')}
                      disabled={downloadingType === 'pdf'}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-teal-600 hover:bg-teal-700 text-white rounded text-xs font-medium transition-colors shadow-xs disabled:opacity-50"
                    >
                      {downloadingType === 'pdf' ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <FileDown className="w-3.5 h-3.5" />
                      )}
                      <span>Export PDF Summary</span>
                    </button>
                  </>
                )}

                {activeReportModal === 'ledger' && (
                  <button
                    onClick={() => handleDownload('reconciliation')}
                    disabled={downloadingType === 'reconciliation'}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-teal-600 hover:bg-teal-700 text-white rounded text-xs font-medium transition-colors shadow-xs disabled:opacity-50"
                  >
                    {downloadingType === 'reconciliation' ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Download className="w-3.5 h-3.5" />
                    )}
                    <span>Export Ledger CSV</span>
                  </button>
                )}
              </div>
            </div>

            {/* Notification messages */}
            {modalSuccess && (
              <div className="mx-6 mt-3 p-2.5 bg-emerald-50 border border-emerald-200 rounded text-xs text-emerald-800">
                {modalSuccess}
              </div>
            )}
            {modalError && (
              <div className="mx-6 mt-3 p-2.5 bg-rose-50 border border-rose-200 rounded text-xs text-rose-800">
                {modalError}
              </div>
            )}

            {/* Modal Body / Table Content */}
            <div className="p-6 overflow-y-auto flex-1 min-h-[300px]">
              {isModalLoading ? (
                <div className="flex flex-col items-center justify-center py-16 text-slate-500">
                  <Loader2 className="w-7 h-7 animate-spin text-teal-600 mb-2" />
                  <p className="text-xs">Generating report data...</p>
                </div>
              ) : activeReportModal === 'invoice' ? (
                /* Invoice Report Table */
                <div>
                  <div className="flex items-center justify-between mb-3 text-xs text-slate-500">
                    <span>
                      Found {modalReportsData?.invoices?.length || 0} invoice records
                    </span>
                    <span>
                      Total Amount:{' '}
                      <strong className="text-slate-900">
                        {formatCurrency(
                          modalReportsData?.summary?.total_invoiced_amount || 0,
                          modalReportsData?.summary?.currency || 'USD'
                        )}
                      </strong>
                    </span>
                  </div>

                  {(!modalReportsData?.invoices || modalReportsData.invoices.length === 0) ? (
                    <div className="py-12 text-center text-slate-500 text-xs">
                      No invoices found for the selected period.
                    </div>
                  ) : (
                    <div className="border border-slate-200 rounded-md overflow-hidden">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
                          <tr>
                            <th className="py-2.5 px-3">Invoice #</th>
                            <th className="py-2.5 px-3">Supplier</th>
                            <th className="py-2.5 px-3">Date</th>
                            <th className="py-2.5 px-3">Due Date</th>
                            <th className="py-2.5 px-3 text-right">Total Amount</th>
                            <th className="py-2.5 px-3 text-center">Status</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {modalReportsData.invoices.map((inv) => (
                            <tr key={inv.id} className="hover:bg-slate-50/60">
                              <td className="py-2.5 px-3 font-semibold text-slate-900">
                                #{inv.invoice_number}
                              </td>
                              <td className="py-2.5 px-3 text-slate-700">{inv.vendor_name}</td>
                              <td className="py-2.5 px-3 text-slate-600">{inv.invoice_date}</td>
                              <td className="py-2.5 px-3 text-slate-600">{inv.due_date || 'N/A'}</td>
                              <td className="py-2.5 px-3 text-right font-medium text-slate-900">
                                {formatCurrency(inv.total_amount, inv.currency)}
                              </td>
                              <td className="py-2.5 px-3 text-center">
                                <span className="inline-flex px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-100 text-slate-700">
                                  {inv.payment_status || 'RECORDED'}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              ) : activeReportModal === 'verification' ? (
                /* Verification Report Table */
                <div>
                  <div className="flex items-center justify-between mb-3 text-xs text-slate-500">
                    <span>
                      Audited {modalReportsData?.invoices?.length || 0} invoice records
                    </span>
                    <span>
                      Anomalies & Mismatches:{' '}
                      <strong className="text-amber-800">
                        {modalReportsData?.summary?.anomalous_count || 0} flagged
                      </strong>
                    </span>
                  </div>

                  {(!modalReportsData?.invoices || modalReportsData.invoices.length === 0) ? (
                    <div className="py-12 text-center text-slate-500 text-xs">
                      No invoices found for the selected period.
                    </div>
                  ) : (
                    <div className="border border-slate-200 rounded-md overflow-hidden">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
                          <tr>
                            <th className="py-2.5 px-3">Invoice #</th>
                            <th className="py-2.5 px-3">Supplier</th>
                            <th className="py-2.5 px-3">Date</th>
                            <th className="py-2.5 px-3 text-right">Amount</th>
                            <th className="py-2.5 px-3 text-center">Integrity Check</th>
                            <th className="py-2.5 px-3">Audit Details</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {modalReportsData.invoices.map((inv) => {
                            const isIssue =
                              inv.payment_status?.includes('OVERDUE') ||
                              inv.payment_status?.includes('UNCONFIRMED') ||
                              inv.payment_status === 'NEEDS_REVIEW';
                            return (
                              <tr key={inv.id} className="hover:bg-slate-50/60">
                                <td className="py-2.5 px-3 font-semibold text-slate-900">
                                  #{inv.invoice_number}
                                </td>
                                <td className="py-2.5 px-3 text-slate-700">{inv.vendor_name}</td>
                                <td className="py-2.5 px-3 text-slate-600">{inv.invoice_date}</td>
                                <td className="py-2.5 px-3 text-right font-medium text-slate-900">
                                  {formatCurrency(inv.total_amount, inv.currency)}
                                </td>
                                <td className="py-2.5 px-3 text-center">
                                  {isIssue ? (
                                    <span className="inline-flex px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-50 text-amber-800 border border-amber-300">
                                      Needs Review
                                    </span>
                                  ) : (
                                    <span className="inline-flex px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-50 text-emerald-800 border border-emerald-300">
                                      Verified
                                    </span>
                                  )}
                                </td>
                                <td className="py-2.5 px-3 text-slate-500 text-[11px]">
                                  {isIssue
                                    ? 'Requires reconciliation or verification review'
                                    : 'Passed arithmetic and header checks'}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              ) : (
                /* Ledger Report Table */
                <div>
                  <div className="flex items-center justify-between mb-3 text-xs text-slate-500">
                    <span>
                      {modalReportsData?.reconciliation_items?.length || 0} reconciliation records
                    </span>
                    <span className="flex items-center gap-3">
                      <span>
                        Matched:{' '}
                        <strong className="text-emerald-700">
                          {modalReportsData?.reconciliation_summary?.matched_count || 0}
                        </strong>
                      </span>
                      <span>
                        Mismatched:{' '}
                        <strong className="text-amber-700">
                          {modalReportsData?.reconciliation_summary?.mismatch_count || 0}
                        </strong>
                      </span>
                      <span>
                        Missing:{' '}
                        <strong className="text-rose-700">
                          {modalReportsData?.reconciliation_summary?.missing_count || 0}
                        </strong>
                      </span>
                    </span>
                  </div>

                  {(!modalReportsData?.reconciliation_items ||
                    modalReportsData.reconciliation_items.length === 0) ? (
                    <div className="py-12 text-center text-slate-500 text-xs">
                      No reconciliation records available. Upload an accounting ledger in the Reconciliation section to view matched and mismatched rows.
                    </div>
                  ) : (
                    <div className="border border-slate-200 rounded-md overflow-hidden">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
                          <tr>
                            <th className="py-2.5 px-3">Batch</th>
                            <th className="py-2.5 px-3">Identifier</th>
                            <th className="py-2.5 px-3">Counterparty</th>
                            <th className="py-2.5 px-3">Date</th>
                            <th className="py-2.5 px-3 text-right">Expected</th>
                            <th className="py-2.5 px-3 text-right">Actual</th>
                            <th className="py-2.5 px-3 text-right">Discrepancy</th>
                            <th className="py-2.5 px-3 text-center">Status</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {modalReportsData.reconciliation_items.map((item) => {
                            const isMatch = item.match_status === 'MATCH';
                            return (
                              <tr key={item.id} className="hover:bg-slate-50/60">
                                <td className="py-2.5 px-3 text-slate-600 max-w-[120px] truncate">
                                  {item.batch_title}
                                </td>
                                <td className="py-2.5 px-3 font-semibold text-slate-900">
                                  {item.record_identifier}
                                </td>
                                <td className="py-2.5 px-3 text-slate-700">
                                  {item.counterparty || 'N/A'}
                                </td>
                                <td className="py-2.5 px-3 text-slate-600">
                                  {item.transaction_date || 'N/A'}
                                </td>
                                <td className="py-2.5 px-3 text-right text-slate-700">
                                  {item.expected_value || '—'}
                                </td>
                                <td className="py-2.5 px-3 text-right text-slate-700">
                                  {item.actual_value || '—'}
                                </td>
                                <td className="py-2.5 px-3 text-right font-medium text-slate-900">
                                  {item.discrepancy_amount
                                    ? formatCurrency(item.discrepancy_amount, item.currency)
                                    : '—'}
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
              )}
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-3 border-t border-slate-200 bg-slate-50/50 flex items-center justify-end">
              <button
                onClick={() => setActiveReportModal(null)}
                className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-800 rounded text-xs font-semibold transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
