import React, { useState, useEffect, useCallback } from 'react';
import {
  BarChart3,
  Download,
  Calendar,
  Building,
  DollarSign,
  FileText,
  CreditCard,
  AlertCircle,
  Filter,
  RefreshCw,
  Loader2,
  FileDown,
  ShieldCheck,
  CheckCircle2,
  PieChart,
  Scale,
  ArrowRight,
  Clock,
} from 'lucide-react';
import {
  getReportsAnalytics,
  downloadInvoicesCsv,
  downloadPaymentsCsv,
  downloadOutstandingCsv,
  downloadReconciliationCsv,
  downloadReportPdf,
} from '../api/reports';

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
  const [reportsData, setReportsData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  // Filter States
  const [datePreset, setDatePreset] = useState('all'); // 'all' | 'this_month' | 'last_month' | 'this_year' | 'custom'
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [vendorFilter, setVendorFilter] = useState('');

  // Active View Tab: 'invoices' | 'payments' | 'vendors' | 'reconciliation' | 'trends' | 'exports'
  const [activeTab, setActiveTab] = useState('invoices');

  // Download Loading States
  const [downloadingType, setDownloadingType] = useState(null);

  // Apply Date Preset
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
    // Client-side date check
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
      setErrorMessage(err.message || 'Failed to load report analytics.');
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
        setSuccessMessage('Executive Summary PDF report downloaded successfully.');
      } else if (type === 'invoices') {
        await downloadInvoicesCsv(params);
        setSuccessMessage('Invoices CSV export downloaded successfully.');
      } else if (type === 'payments') {
        await downloadPaymentsCsv(params);
        setSuccessMessage('Payments CSV export downloaded successfully.');
      } else if (type === 'outstanding') {
        await downloadOutstandingCsv(params);
        setSuccessMessage('Outstanding Invoices CSV export downloaded successfully.');
      } else if (type === 'reconciliation') {
        await downloadReconciliationCsv(params);
        setSuccessMessage('Reconciliation CSV export downloaded successfully.');
      }
      setTimeout(() => setSuccessMessage(''), 4500);
    } catch (err) {
      setErrorMessage(err.message || `Failed to export ${type.toUpperCase()}.`);
    } finally {
      setDownloadingType(null);
    }
  };

  const summary = reportsData?.summary || {
    period_label: 'All Time',
    total_invoices_count: 0,
    total_invoiced_amount: '0.00',
    total_payments_count: 0,
    total_paid_amount: '0.00',
    total_outstanding_balance: '0.00',
    overdue_count: 0,
    overdue_amount: '0.00',
    currency: 'USD',
    status_counts: {
      PAID: 0,
      PARTIAL: 0,
      UNPAID: 0,
      DUE_SOON: 0,
      OVERDUE: 0,
    },
  };

  const statusCounts = summary.status_counts || {
    PAID: 0,
    PARTIAL: 0,
    UNPAID: 0,
    DUE_SOON: 0,
    OVERDUE: 0,
  };

  const totalStatusInvoices =
    (statusCounts.PAID || 0) +
    (statusCounts.PARTIAL || 0) +
    (statusCounts.UNPAID || 0) +
    (statusCounts.DUE_SOON || 0) +
    (statusCounts.OVERDUE || 0);

  const getStatusPercent = (count) => {
    if (!totalStatusInvoices || totalStatusInvoices === 0) return 0;
    return Math.round((count / totalStatusInvoices) * 100);
  };

  const vendorBreakdown = reportsData?.vendor_breakdown || [];
  const monthlyTrends = reportsData?.monthly_trends || [];
  const reportInvoices = reportsData?.invoices || [];
  const reportPayments = reportsData?.payments || [];
  const reconcileSummary = reportsData?.reconciliation_summary || {
    total_batches: 0,
    total_records: 0,
    matched_count: 0,
    mismatch_count: 0,
    missing_count: 0,
    duplicate_count: 0,
    pending_review_count: 0,
  };
  const reconcileItems = reportsData?.reconciliation_items || [];

  // Chart max value calculation
  const maxTrendValue = Math.max(
    1,
    ...monthlyTrends.map((t) =>
      Math.max(parseFloat(t.invoiced_amount || 0), parseFloat(t.paid_amount || 0))
    )
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Reports & Analytics</h1>
          <p className="text-sm text-slate-500 mt-1">
            Audited financial reporting, cash flow distribution, ledger reconciliation, and spreadsheet exports.
          </p>
        </div>

        {/* Quick Export Actions */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => handleDownload('pdf')}
            disabled={downloadingType !== null}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white rounded-md text-xs font-medium transition-colors shadow-xs"
          >
            {downloadingType === 'pdf' ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <FileDown className="w-3.5 h-3.5 text-teal-400" />
            )}
            <span>Export PDF</span>
          </button>

          <button
            onClick={() => handleDownload('invoices')}
            disabled={downloadingType !== null}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-300 hover:bg-slate-50 disabled:opacity-50 text-slate-700 rounded-md text-xs font-medium transition-colors shadow-xs"
          >
            {downloadingType === 'invoices' ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin text-teal-600" />
            ) : (
              <Download className="w-3.5 h-3.5 text-teal-600" />
            )}
            <span>Invoices CSV</span>
          </button>

          <button
            onClick={() => handleDownload('payments')}
            disabled={downloadingType !== null}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-300 hover:bg-slate-50 disabled:opacity-50 text-slate-700 rounded-md text-xs font-medium transition-colors shadow-xs"
          >
            {downloadingType === 'payments' ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin text-teal-600" />
            ) : (
              <Download className="w-3.5 h-3.5 text-teal-600" />
            )}
            <span>Payments CSV</span>
          </button>

          <button
            onClick={() => handleDownload('reconciliation')}
            disabled={downloadingType !== null}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-300 hover:bg-slate-50 disabled:opacity-50 text-slate-700 rounded-md text-xs font-medium transition-colors shadow-xs"
          >
            {downloadingType === 'reconciliation' ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin text-teal-600" />
            ) : (
              <Scale className="w-3.5 h-3.5 text-teal-600" />
            )}
            <span>Reconciliation CSV</span>
          </button>
        </div>
      </div>

      {/* Global Notifications */}
      {errorMessage && (
        <div className="flex items-center gap-2 p-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-md">
          <AlertCircle className="w-5 h-5 shrink-0 text-red-600" />
          <span>{errorMessage}</span>
        </div>
      )}

      {successMessage && (
        <div className="flex items-center gap-2 p-3 text-sm text-teal-800 bg-teal-50 border border-teal-200 rounded-md">
          <CheckCircle2 className="w-5 h-5 shrink-0 text-teal-600" />
          <span>{successMessage}</span>
        </div>
      )}

      {/* Multi-Currency Notification */}
      {summary.has_multiple_currencies && (
        <div className="p-3 bg-amber-50 border border-amber-200 rounded-md text-xs text-amber-900 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="font-semibold">Multi-Currency Portfolio:</span>
            <span>Multiple currencies detected. Individual invoice currencies are preserved in tables and CSV exports.</span>
          </div>
          <span className="font-semibold text-amber-800">Primary: {summary.currency}</span>
        </div>
      )}

      {/* Filter Toolbar with Date Presets */}
      <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-xs space-y-4">
        {/* Presets and Toolbar Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-700">
            <Filter className="w-4 h-4 text-teal-600" />
            <span>Reporting Period & Filters</span>
            <span className="font-normal text-slate-400">({summary.period_label})</span>
          </div>

          {/* Quick Presets */}
          <div className="flex flex-wrap items-center gap-1.5">
            {[
              { id: 'all', label: 'All Time' },
              { id: 'this_month', label: 'This Month' },
              { id: 'last_month', label: 'Last Month' },
              { id: 'this_year', label: 'This Year' },
              { id: 'custom', label: 'Custom' },
            ].map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => handlePresetChange(p.id)}
                className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                  datePreset === p.id
                    ? 'bg-slate-900 text-white shadow-xs'
                    : 'bg-slate-100 hover:bg-slate-200 text-slate-600'
                }`}
              >
                {p.label}
              </button>
            ))}

            {(startDate || endDate || vendorFilter) && (
              <button
                onClick={handleResetFilters}
                className="text-xs text-teal-700 hover:underline font-medium ml-2"
              >
                Reset
              </button>
            )}
          </div>
        </div>

        {/* Input Controls */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label className="block text-[11px] font-semibold text-slate-500 uppercase mb-1">
              Start Date
            </label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => {
                setStartDate(e.target.value);
                setDatePreset('custom');
              }}
              className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded-md text-xs text-slate-800 focus:outline-hidden focus:ring-1 focus:ring-teal-500"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-500 uppercase mb-1">
              End Date
            </label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => {
                setEndDate(e.target.value);
                setDatePreset('custom');
              }}
              className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded-md text-xs text-slate-800 focus:outline-hidden focus:ring-1 focus:ring-teal-500"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-500 uppercase mb-1">
              Filter by Vendor / Supplier
            </label>
            <input
              type="text"
              placeholder="e.g. Acme Corp..."
              value={vendorFilter}
              onChange={(e) => setVendorFilter(e.target.value)}
              className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded-md text-xs text-slate-800 focus:outline-hidden focus:ring-1 focus:ring-teal-500"
            />
          </div>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Invoiced */}
        <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-xs">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Total Invoiced
          </span>
          <div className="mt-2">
            <span className="text-2xl font-bold text-slate-900">
              {formatCurrency(summary.total_invoiced_amount, summary.currency)}
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            {summary.total_invoices_count} invoices in period
          </p>
        </div>

        {/* Paid */}
        <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-xs">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Total Paid
          </span>
          <div className="mt-2">
            <span className="text-2xl font-bold text-teal-700">
              {formatCurrency(summary.total_paid_amount, summary.currency)}
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            {summary.total_payments_count} recorded payments
          </p>
        </div>

        {/* Outstanding */}
        <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-xs">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Outstanding Balance
          </span>
          <div className="mt-2">
            <span className="text-2xl font-bold text-slate-900">
              {formatCurrency(summary.total_outstanding_balance, summary.currency)}
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-500">Unsettled commitments</p>
        </div>

        {/* Overdue */}
        <div className="bg-white border border-rose-200/80 rounded-lg p-5 shadow-xs">
          <span className="text-xs font-semibold text-rose-700 uppercase tracking-wider">
            Overdue Amount
          </span>
          <div className="mt-2">
            <span className="text-2xl font-bold text-slate-900">
              {formatCurrency(summary.overdue_amount, summary.currency)}
            </span>
          </div>
          <p className="mt-1 text-xs font-medium text-rose-600">
            {summary.overdue_count} overdue invoices
          </p>
        </div>
      </div>

      {/* Visual Charts: Monthly Cash Flow & Invoice Status Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Monthly Cash Flow Bars (2 cols) */}
        <div className="lg:col-span-2 bg-white border border-slate-200 rounded-lg p-6 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-4">
              <div>
                <h3 className="text-sm font-semibold text-slate-900">Monthly Cash Flow Comparison</h3>
                <p className="text-xs text-slate-500">Invoiced amounts vs payments received</p>
              </div>
              <div className="flex items-center gap-4 text-xs font-medium text-slate-600">
                <div className="flex items-center gap-1.5">
                  <div className="w-3 h-3 bg-teal-600 rounded-xs" />
                  <span>Invoiced</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="w-3 h-3 bg-slate-400 rounded-xs" />
                  <span>Paid</span>
                </div>
              </div>
            </div>

            {monthlyTrends.length === 0 ? (
              <div className="h-40 flex items-center justify-center text-xs text-slate-400">
                No monthly trend data recorded for selected dates.
              </div>
            ) : (
              <div className="grid grid-cols-6 gap-2 sm:gap-4 pt-6 pb-2 border-b border-slate-100">
                {monthlyTrends.map((m) => {
                  const invVal = parseFloat(m.invoiced_amount || 0);
                  const paidVal = parseFloat(m.paid_amount || 0);
                  const invHeight = Math.max(4, Math.round((invVal / maxTrendValue) * 110));
                  const paidHeight = Math.max(4, Math.round((paidVal / maxTrendValue) * 110));

                  return (
                    <div key={m.month_key} className="flex flex-col items-center">
                      <div className="h-28 flex items-end justify-center gap-1.5 w-full">
                        {/* Invoiced Bar */}
                        <div className="relative group flex flex-col items-center w-3 sm:w-5">
                          <div
                            className="w-full bg-teal-600 hover:bg-teal-700 rounded-t-xs transition-all duration-300"
                            style={{ height: `${invHeight}px` }}
                          />
                          <div className="absolute bottom-full mb-1 hidden group-hover:block z-10 px-2 py-1 bg-slate-900 text-white text-[10px] rounded whitespace-nowrap shadow-md">
                            Invoiced: {formatCurrency(invVal, summary.currency)}
                          </div>
                        </div>
                        {/* Paid Bar */}
                        <div className="relative group flex flex-col items-center w-3 sm:w-5">
                          <div
                            className="w-full bg-slate-400 hover:bg-slate-500 rounded-t-xs transition-all duration-300"
                            style={{ height: `${paidHeight}px` }}
                          />
                          <div className="absolute bottom-full mb-1 hidden group-hover:block z-10 px-2 py-1 bg-slate-900 text-white text-[10px] rounded whitespace-nowrap shadow-md">
                            Paid: {formatCurrency(paidVal, summary.currency)}
                          </div>
                        </div>
                      </div>
                      <span className="text-[10px] font-medium text-slate-600 mt-2 text-center whitespace-nowrap">
                        {m.month_label}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
          <div className="pt-3 text-[11px] text-slate-400 flex items-center justify-between">
            <span>Aggregated across user invoices and payments</span>
            <span>Source: Verified Ledger</span>
          </div>
        </div>

        {/* Invoice Status Distribution (1 col) */}
        <div className="bg-white border border-slate-200 rounded-lg p-6 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-slate-900">Invoice Status Distribution</h3>
              <PieChart className="w-4 h-4 text-slate-400" />
            </div>

            {totalStatusInvoices === 0 ? (
              <div className="h-40 flex items-center justify-center text-xs text-slate-400">
                No invoices found in this period.
              </div>
            ) : (
              <div className="space-y-4">
                {/* Horizontal Segmented Progress Bar */}
                <div className="h-3 w-full bg-slate-100 rounded-full overflow-hidden flex shadow-inner">
                  {statusCounts.PAID > 0 && (
                    <div
                      style={{ width: `${getStatusPercent(statusCounts.PAID)}%` }}
                      className="bg-teal-600"
                      title={`Paid: ${statusCounts.PAID}`}
                    />
                  )}
                  {statusCounts.PARTIAL > 0 && (
                    <div
                      style={{ width: `${getStatusPercent(statusCounts.PARTIAL)}%` }}
                      className="bg-amber-500"
                      title={`Partially Paid: ${statusCounts.PARTIAL}`}
                    />
                  )}
                  {statusCounts.DUE_SOON > 0 && (
                    <div
                      style={{ width: `${getStatusPercent(statusCounts.DUE_SOON)}%` }}
                      className="bg-sky-500"
                      title={`Due Soon: ${statusCounts.DUE_SOON}`}
                    />
                  )}
                  {statusCounts.UNPAID > 0 && (
                    <div
                      style={{ width: `${getStatusPercent(statusCounts.UNPAID)}%` }}
                      className="bg-slate-400"
                      title={`Unpaid: ${statusCounts.UNPAID}`}
                    />
                  )}
                  {statusCounts.OVERDUE > 0 && (
                    <div
                      style={{ width: `${getStatusPercent(statusCounts.OVERDUE)}%` }}
                      className="bg-rose-500"
                      title={`Overdue: ${statusCounts.OVERDUE}`}
                    />
                  )}
                </div>

                {/* Status Legend & Breakdown */}
                <div className="space-y-2 text-xs">
                  <div className="flex items-center justify-between py-1 border-b border-slate-100">
                    <div className="flex items-center gap-2">
                      <div className="w-2.5 h-2.5 rounded-full bg-teal-600" />
                      <span className="text-slate-700 font-medium">Fully Paid</span>
                    </div>
                    <span className="font-semibold text-slate-900">
                      {statusCounts.PAID || 0} ({getStatusPercent(statusCounts.PAID)}%)
                    </span>
                  </div>

                  <div className="flex items-center justify-between py-1 border-b border-slate-100">
                    <div className="flex items-center gap-2">
                      <div className="w-2.5 h-2.5 rounded-full bg-amber-500" />
                      <span className="text-slate-700 font-medium">Partially Paid</span>
                    </div>
                    <span className="font-semibold text-slate-900">
                      {statusCounts.PARTIAL || 0} ({getStatusPercent(statusCounts.PARTIAL)}%)
                    </span>
                  </div>

                  <div className="flex items-center justify-between py-1 border-b border-slate-100">
                    <div className="flex items-center gap-2">
                      <div className="w-2.5 h-2.5 rounded-full bg-sky-500" />
                      <span className="text-slate-700 font-medium">Due Soon (&le; 7d)</span>
                    </div>
                    <span className="font-semibold text-slate-900">
                      {statusCounts.DUE_SOON || 0} ({getStatusPercent(statusCounts.DUE_SOON)}%)
                    </span>
                  </div>

                  <div className="flex items-center justify-between py-1 border-b border-slate-100">
                    <div className="flex items-center gap-2">
                      <div className="w-2.5 h-2.5 rounded-full bg-slate-400" />
                      <span className="text-slate-700 font-medium">Unpaid</span>
                    </div>
                    <span className="font-semibold text-slate-900">
                      {statusCounts.UNPAID || 0} ({getStatusPercent(statusCounts.UNPAID)}%)
                    </span>
                  </div>

                  <div className="flex items-center justify-between py-1">
                    <div className="flex items-center gap-2">
                      <div className="w-2.5 h-2.5 rounded-full bg-rose-500" />
                      <span className="text-rose-700 font-medium">Overdue</span>
                    </div>
                    <span className="font-semibold text-rose-700">
                      {statusCounts.OVERDUE || 0} ({getStatusPercent(statusCounts.OVERDUE)}%)
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
          <div className="pt-3 border-t border-slate-100 text-[11px] text-slate-400">
            Total Invoices Evaluated: {totalStatusInvoices}
          </div>
        </div>
      </div>

      {/* Main Tabbed Report Views */}
      <div className="bg-white border border-slate-200 rounded-lg shadow-xs overflow-hidden">
        {/* Navigation Tabs */}
        <div className="p-4 border-b border-slate-200 bg-slate-50/50 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-1.5">
            <button
              onClick={() => setActiveTab('invoices')}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                activeTab === 'invoices'
                  ? 'bg-slate-900 text-white shadow-xs'
                  : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-100'
              }`}
            >
              Invoices Report ({reportInvoices.length})
            </button>

            <button
              onClick={() => setActiveTab('payments')}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                activeTab === 'payments'
                  ? 'bg-slate-900 text-white shadow-xs'
                  : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-100'
              }`}
            >
              Payments Report ({reportPayments.length})
            </button>

            <button
              onClick={() => setActiveTab('vendors')}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                activeTab === 'vendors'
                  ? 'bg-slate-900 text-white shadow-xs'
                  : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-100'
              }`}
            >
              Vendor Summary ({vendorBreakdown.length})
            </button>

            <button
              onClick={() => setActiveTab('reconciliation')}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                activeTab === 'reconciliation'
                  ? 'bg-slate-900 text-white shadow-xs'
                  : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-100'
              }`}
            >
              Reconciliation ({reconcileSummary.total_records})
            </button>

            <button
              onClick={() => setActiveTab('trends')}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                activeTab === 'trends'
                  ? 'bg-slate-900 text-white shadow-xs'
                  : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-100'
              }`}
            >
              Monthly Cash Flow ({monthlyTrends.length})
            </button>

            <button
              onClick={() => setActiveTab('exports')}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                activeTab === 'exports'
                  ? 'bg-teal-700 text-white shadow-xs'
                  : 'bg-white border border-slate-200 text-teal-800 hover:bg-teal-50'
              }`}
            >
              Export Hub
            </button>
          </div>

          <div className="hidden sm:flex items-center gap-1.5 text-xs text-slate-400">
            <ShieldCheck className="w-3.5 h-3.5 text-teal-600" />
            <span>Formula injection protected</span>
          </div>
        </div>

        {/* Tab Content */}
        {isLoading ? (
          <div className="p-12 text-center text-slate-500">
            <Loader2 className="w-8 h-8 animate-spin mx-auto text-teal-600 mb-2" />
            <p className="text-sm">Compiling financial report data...</p>
          </div>
        ) : activeTab === 'invoices' ? (
          /* TAB 1: Invoices Report Table */
          reportInvoices.length === 0 ? (
            <div className="p-12 text-center text-xs text-slate-500">
              No invoices found for the selected reporting period.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-slate-700 divide-y divide-slate-200">
                <thead className="bg-slate-50 text-xs font-semibold text-slate-600 uppercase tracking-wider">
                  <tr>
                    <th className="px-5 py-3.5">Invoice #</th>
                    <th className="px-5 py-3.5">Supplier / Vendor</th>
                    <th className="px-5 py-3.5">Invoice Date</th>
                    <th className="px-5 py-3.5">Due Date</th>
                    <th className="px-5 py-3.5 text-right">Total Amount</th>
                    <th className="px-5 py-3.5 text-right">Amount Paid</th>
                    <th className="px-5 py-3.5 text-right">Balance Due</th>
                    <th className="px-5 py-3.5 text-center">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {reportInvoices.map((inv) => (
                    <tr key={inv.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="px-5 py-3.5 font-semibold text-slate-900 whitespace-nowrap">
                        {inv.invoice_number}
                      </td>
                      <td className="px-5 py-3.5 text-slate-800 whitespace-nowrap">
                        {inv.vendor_name}
                      </td>
                      <td className="px-5 py-3.5 text-slate-600 whitespace-nowrap">
                        {inv.invoice_date}
                      </td>
                      <td className="px-5 py-3.5 text-slate-600 whitespace-nowrap">
                        {inv.due_date || 'N/A'}
                      </td>
                      <td className="px-5 py-3.5 text-right font-medium text-slate-900 whitespace-nowrap">
                        {formatCurrency(inv.total_amount, inv.currency)}
                      </td>
                      <td className="px-5 py-3.5 text-right text-teal-700 font-medium whitespace-nowrap">
                        {formatCurrency(inv.total_paid, inv.currency)}
                      </td>
                      <td className="px-5 py-3.5 text-right font-semibold text-slate-900 whitespace-nowrap">
                        {formatCurrency(inv.balance_due, inv.currency)}
                      </td>
                      <td className="px-5 py-3.5 text-center whitespace-nowrap">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold ${
                            inv.payment_status === 'PAID'
                              ? 'bg-teal-50 text-teal-700 border border-teal-200'
                              : inv.payment_status === 'PARTIAL'
                              ? 'bg-amber-50 text-amber-700 border border-amber-200'
                              : inv.payment_status === 'OVERDUE'
                              ? 'bg-rose-50 text-rose-700 border border-rose-200'
                              : inv.payment_status === 'DUE_SOON'
                              ? 'bg-sky-50 text-sky-700 border border-sky-200'
                              : 'bg-slate-100 text-slate-700 border border-slate-200'
                          }`}
                        >
                          {inv.payment_status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        ) : activeTab === 'payments' ? (
          /* TAB 2: Payments Report Table */
          reportPayments.length === 0 ? (
            <div className="p-12 text-center text-xs text-slate-500">
              No payments recorded for the selected reporting period.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-slate-700 divide-y divide-slate-200">
                <thead className="bg-slate-50 text-xs font-semibold text-slate-600 uppercase tracking-wider">
                  <tr>
                    <th className="px-5 py-3.5">Payment Date</th>
                    <th className="px-5 py-3.5">Invoice #</th>
                    <th className="px-5 py-3.5">Supplier / Vendor</th>
                    <th className="px-5 py-3.5 text-right">Amount Paid</th>
                    <th className="px-5 py-3.5">Method</th>
                    <th className="px-5 py-3.5">Reference Number</th>
                    <th className="px-5 py-3.5">Notes</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {reportPayments.map((p) => (
                    <tr key={p.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="px-5 py-3.5 font-medium text-slate-900 whitespace-nowrap">
                        {p.payment_date}
                      </td>
                      <td className="px-5 py-3.5 font-semibold text-slate-800 whitespace-nowrap">
                        {p.invoice_number}
                      </td>
                      <td className="px-5 py-3.5 text-slate-700 whitespace-nowrap">
                        {p.vendor_name}
                      </td>
                      <td className="px-5 py-3.5 text-right font-semibold text-teal-700 whitespace-nowrap">
                        {formatCurrency(p.amount, p.currency)}
                      </td>
                      <td className="px-5 py-3.5 text-slate-600 whitespace-nowrap">
                        {p.payment_method}
                      </td>
                      <td className="px-5 py-3.5 text-slate-500 text-xs whitespace-nowrap">
                        {p.reference || '-'}
                      </td>
                      <td className="px-5 py-3.5 text-slate-500 text-xs truncate max-w-xs">
                        {p.notes || '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        ) : activeTab === 'vendors' ? (
          /* TAB 3: Vendor Breakdown Table */
          vendorBreakdown.length === 0 ? (
            <div className="p-12 text-center text-xs text-slate-500">
              No vendor records found for the selected reporting period.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-slate-700 divide-y divide-slate-200">
                <thead className="bg-slate-50 text-xs font-semibold text-slate-600 uppercase tracking-wider">
                  <tr>
                    <th className="px-6 py-3.5">Supplier / Vendor</th>
                    <th className="px-6 py-3.5 text-center">Invoices</th>
                    <th className="px-6 py-3.5 text-right">Total Invoiced</th>
                    <th className="px-6 py-3.5 text-right">Total Paid</th>
                    <th className="px-6 py-3.5 text-right">Balance Due</th>
                    <th className="px-6 py-3.5 text-center">Overdue</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {vendorBreakdown.map((v) => (
                    <tr key={v.vendor_name} className="hover:bg-slate-50/70 transition-colors">
                      <td className="px-6 py-4 font-medium text-slate-900 whitespace-nowrap">
                        {v.vendor_name}
                      </td>
                      <td className="px-6 py-4 text-center whitespace-nowrap text-slate-600">
                        {v.invoice_count}
                      </td>
                      <td className="px-6 py-4 text-right font-semibold text-slate-900 whitespace-nowrap">
                        {formatCurrency(v.total_invoiced, summary.currency)}
                      </td>
                      <td className="px-6 py-4 text-right text-teal-700 font-medium whitespace-nowrap">
                        {formatCurrency(v.total_paid, summary.currency)}
                      </td>
                      <td className="px-6 py-4 text-right font-semibold text-slate-900 whitespace-nowrap">
                        {formatCurrency(v.outstanding_balance, summary.currency)}
                      </td>
                      <td className="px-6 py-4 text-center whitespace-nowrap">
                        {v.overdue_count > 0 ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
                            {v.overdue_count} overdue
                          </span>
                        ) : (
                          <span className="text-slate-400 text-xs">0</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        ) : activeTab === 'reconciliation' ? (
          /* TAB 4: Reconciliation Report */
          <div className="p-6 space-y-6">
            {/* KPI Cards for Reconciliation */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="p-3 bg-teal-50/70 border border-teal-200 rounded-md">
                <span className="text-[11px] font-semibold text-teal-800 uppercase">Exact Matches</span>
                <p className="text-lg font-bold text-teal-900 mt-1">{reconcileSummary.matched_count}</p>
              </div>

              <div className="p-3 bg-amber-50/70 border border-amber-200 rounded-md">
                <span className="text-[11px] font-semibold text-amber-800 uppercase">Amount Mismatches</span>
                <p className="text-lg font-bold text-amber-900 mt-1">{reconcileSummary.mismatch_count}</p>
              </div>

              <div className="p-3 bg-rose-50/70 border border-rose-200 rounded-md">
                <span className="text-[11px] font-semibold text-rose-800 uppercase">Missing Records</span>
                <p className="text-lg font-bold text-rose-900 mt-1">{reconcileSummary.missing_count}</p>
              </div>

              <div className="p-3 bg-slate-50 border border-slate-200 rounded-md">
                <span className="text-[11px] font-semibold text-slate-700 uppercase">Awaiting Review</span>
                <p className="text-lg font-bold text-slate-900 mt-1">{reconcileSummary.pending_review_count}</p>
              </div>
            </div>

            {/* Reconciliation Items Table */}
            {reconcileItems.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500 border border-dashed border-slate-200 rounded-lg">
                <Scale className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                <p className="font-medium text-slate-700">No reconciliation records found.</p>
                <p className="mt-1">
                  Upload an Accounting Ledger or Bank Statement in the Reconciliation Centre to begin matching.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto border border-slate-200 rounded-md">
                <table className="w-full text-left text-sm text-slate-700 divide-y divide-slate-200">
                  <thead className="bg-slate-50 text-xs font-semibold text-slate-600 uppercase tracking-wider">
                    <tr>
                      <th className="px-4 py-3">Batch Title</th>
                      <th className="px-4 py-3">Record Identifier</th>
                      <th className="px-4 py-3">Counterparty</th>
                      <th className="px-4 py-3">Date</th>
                      <th className="px-4 py-3 text-right">Expected</th>
                      <th className="px-4 py-3 text-right">Actual</th>
                      <th className="px-4 py-3 text-right">Discrepancy</th>
                      <th className="px-4 py-3 text-center">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 bg-white">
                    {reconcileItems.map((item) => (
                      <tr key={item.id} className="hover:bg-slate-50/70 transition-colors">
                        <td className="px-4 py-3 font-medium text-slate-900 whitespace-nowrap">
                          {item.batch_title}
                        </td>
                        <td className="px-4 py-3 text-slate-700 whitespace-nowrap">
                          {item.record_identifier}
                        </td>
                        <td className="px-4 py-3 text-slate-800 whitespace-nowrap">
                          {item.counterparty || '-'}
                        </td>
                        <td className="px-4 py-3 text-slate-600 whitespace-nowrap">
                          {item.transaction_date || '-'}
                        </td>
                        <td className="px-4 py-3 text-right text-slate-700 whitespace-nowrap">
                          {item.expected_value || '-'}
                        </td>
                        <td className="px-4 py-3 text-right font-medium text-slate-900 whitespace-nowrap">
                          {item.actual_value || '-'}
                        </td>
                        <td className="px-4 py-3 text-right text-rose-700 font-semibold whitespace-nowrap">
                          {item.discrepancy_amount ? formatCurrency(item.discrepancy_amount, item.currency) : '-'}
                        </td>
                        <td className="px-4 py-3 text-center whitespace-nowrap">
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold ${
                              item.match_status === 'MATCHED'
                                ? 'bg-teal-50 text-teal-700 border border-teal-200'
                                : item.match_status === 'AMOUNT_MISMATCH'
                                ? 'bg-amber-50 text-amber-700 border border-amber-200'
                                : 'bg-rose-50 text-rose-700 border border-rose-200'
                            }`}
                          >
                            {item.match_status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ) : activeTab === 'trends' ? (
          /* TAB 5: Monthly Trends Table */
          monthlyTrends.length === 0 ? (
            <div className="p-12 text-center text-xs text-slate-500">
              No trend data available for the selected dates.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-slate-700 divide-y divide-slate-200">
                <thead className="bg-slate-50 text-xs font-semibold text-slate-600 uppercase tracking-wider">
                  <tr>
                    <th className="px-6 py-3.5">Month</th>
                    <th className="px-6 py-3.5 text-center">Invoices</th>
                    <th className="px-6 py-3.5 text-right">Invoiced Amount</th>
                    <th className="px-6 py-3.5 text-center">Payments</th>
                    <th className="px-6 py-3.5 text-right">Paid Amount</th>
                    <th className="px-6 py-3.5 text-right">Net Cash Difference</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {monthlyTrends.map((t) => {
                    const invAmt = parseFloat(t.invoiced_amount || 0);
                    const paidAmt = parseFloat(t.paid_amount || 0);
                    const diff = paidAmt - invAmt;

                    return (
                      <tr key={t.month_key} className="hover:bg-slate-50/70 transition-colors">
                        <td className="px-6 py-4 font-semibold text-slate-900 whitespace-nowrap">
                          {t.month_label}
                        </td>
                        <td className="px-6 py-4 text-center text-slate-600 whitespace-nowrap">
                          {t.invoiced_count}
                        </td>
                        <td className="px-6 py-4 text-right font-medium text-slate-900 whitespace-nowrap">
                          {formatCurrency(invAmt, summary.currency)}
                        </td>
                        <td className="px-6 py-4 text-center text-slate-600 whitespace-nowrap">
                          {t.paid_count}
                        </td>
                        <td className="px-6 py-4 text-right font-medium text-teal-700 whitespace-nowrap">
                          {formatCurrency(paidAmt, summary.currency)}
                        </td>
                        <td className="px-6 py-4 text-right font-semibold whitespace-nowrap">
                          <span className={diff >= 0 ? 'text-teal-700' : 'text-slate-600'}>
                            {diff >= 0 ? `+${formatCurrency(diff, summary.currency)}` : formatCurrency(diff, summary.currency)}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )
        ) : (
          /* TAB 6: Export Hub */
          <div className="p-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* PDF Report Card */}
            <div className="p-5 border border-slate-200 rounded-lg bg-slate-50/50 flex flex-col justify-between space-y-4">
              <div>
                <div className="w-8 h-8 rounded bg-slate-900 text-white flex items-center justify-center mb-3">
                  <FileDown className="w-4 h-4 text-teal-400" />
                </div>
                <h4 className="text-sm font-semibold text-slate-900">Executive Financial Report (PDF)</h4>
                <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                  Generates an executive PDF document containing account summary metrics, status distribution,
                  and top vendor breakdown.
                </p>
              </div>
              <button
                onClick={() => handleDownload('pdf')}
                disabled={downloadingType !== null}
                className="w-full inline-flex items-center justify-center gap-1.5 px-4 py-2 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white rounded-md text-xs font-medium transition-colors shadow-xs"
              >
                {downloadingType === 'pdf' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
                <span>Download PDF Summary</span>
              </button>
            </div>

            {/* Invoices CSV Card */}
            <div className="p-5 border border-slate-200 rounded-lg bg-slate-50/50 flex flex-col justify-between space-y-4">
              <div>
                <div className="w-8 h-8 rounded bg-teal-50 text-teal-700 flex items-center justify-center mb-3">
                  <FileText className="w-4 h-4" />
                </div>
                <h4 className="text-sm font-semibold text-slate-900">Complete Invoices Register (CSV)</h4>
                <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                  Exports all saved invoices with totals, subtotals, tax breakdown, payments,
                  and ML screening flags with formula injection protection.
                </p>
              </div>
              <button
                onClick={() => handleDownload('invoices')}
                disabled={downloadingType !== null}
                className="w-full inline-flex items-center justify-center gap-1.5 px-4 py-2 bg-white border border-slate-300 hover:bg-slate-100 disabled:opacity-50 text-slate-700 rounded-md text-xs font-medium transition-colors shadow-xs"
              >
                {downloadingType === 'invoices' ? <Loader2 className="w-3.5 h-3.5 animate-spin text-teal-600" /> : <Download className="w-3.5 h-3.5 text-teal-600" />}
                <span>Download Invoices CSV</span>
              </button>
            </div>

            {/* Payments CSV Card */}
            <div className="p-5 border border-slate-200 rounded-lg bg-slate-50/50 flex flex-col justify-between space-y-4">
              <div>
                <div className="w-8 h-8 rounded bg-teal-50 text-teal-700 flex items-center justify-center mb-3">
                  <CreditCard className="w-4 h-4" />
                </div>
                <h4 className="text-sm font-semibold text-slate-900">Payment Transactions (CSV)</h4>
                <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                  Full transaction log of recorded settlements, payment methods, transaction
                  reference numbers, and notes.
                </p>
              </div>
              <button
                onClick={() => handleDownload('payments')}
                disabled={downloadingType !== null}
                className="w-full inline-flex items-center justify-center gap-1.5 px-4 py-2 bg-white border border-slate-300 hover:bg-slate-100 disabled:opacity-50 text-slate-700 rounded-md text-xs font-medium transition-colors shadow-xs"
              >
                {downloadingType === 'payments' ? <Loader2 className="w-3.5 h-3.5 animate-spin text-teal-600" /> : <Download className="w-3.5 h-3.5 text-teal-600" />}
                <span>Download Payments CSV</span>
              </button>
            </div>

            {/* Outstanding CSV Card */}
            <div className="p-5 border border-slate-200 rounded-lg bg-slate-50/50 flex flex-col justify-between space-y-4">
              <div>
                <div className="w-8 h-8 rounded bg-rose-50 text-rose-700 flex items-center justify-center mb-3">
                  <DollarSign className="w-4 h-4" />
                </div>
                <h4 className="text-sm font-semibold text-slate-900">Outstanding & Overdue Invoices (CSV)</h4>
                <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                  Focused list of all unpaid and partially paid balances, showing days overdue
                  and exact remaining liabilities.
                </p>
              </div>
              <button
                onClick={() => handleDownload('outstanding')}
                disabled={downloadingType !== null}
                className="w-full inline-flex items-center justify-center gap-1.5 px-4 py-2 bg-white border border-slate-300 hover:bg-slate-100 disabled:opacity-50 text-slate-700 rounded-md text-xs font-medium transition-colors shadow-xs"
              >
                {downloadingType === 'outstanding' ? <Loader2 className="w-3.5 h-3.5 animate-spin text-rose-600" /> : <Download className="w-3.5 h-3.5 text-rose-600" />}
                <span>Download Outstanding CSV</span>
              </button>
            </div>

            {/* Reconciliation CSV Card */}
            <div className="p-5 border border-slate-200 rounded-lg bg-slate-50/50 flex flex-col justify-between space-y-4">
              <div>
                <div className="w-8 h-8 rounded bg-teal-50 text-teal-700 flex items-center justify-center mb-3">
                  <Scale className="w-4 h-4" />
                </div>
                <h4 className="text-sm font-semibold text-slate-900">Reconciliation Discrepancy Log (CSV)</h4>
                <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                  Exports ledger and bank statement matches, amount discrepancies, missing rows,
                  and audit evidence.
                </p>
              </div>
              <button
                onClick={() => handleDownload('reconciliation')}
                disabled={downloadingType !== null}
                className="w-full inline-flex items-center justify-center gap-1.5 px-4 py-2 bg-white border border-slate-300 hover:bg-slate-100 disabled:opacity-50 text-slate-700 rounded-md text-xs font-medium transition-colors shadow-xs"
              >
                {downloadingType === 'reconciliation' ? <Loader2 className="w-3.5 h-3.5 animate-spin text-teal-600" /> : <Download className="w-3.5 h-3.5 text-teal-600" />}
                <span>Download Reconciliation CSV</span>
              </button>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex items-center justify-between text-xs text-slate-500">
          <span>Active Period: {summary.period_label}</span>
          <span>Verified against database records</span>
        </div>
      </div>
    </div>
  );
}
