import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  DollarSign,
  FileCheck,
  AlertTriangle,
  Clock,
  Upload,
  BarChart3,
  Loader2,
  AlertCircle,
  FileText,
  ChevronRight,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { getDashboardAnalytics } from '../api/reports';

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

function formatNearestDueDate(nearestDueDateStr, upcomingCount) {
  if (!nearestDueDateStr) {
    return 'No upcoming due dates';
  }
  const parts = String(nearestDueDateStr).split('-');
  if (parts.length === 3) {
    const y = parseInt(parts[0], 10);
    const m = parseInt(parts[1], 10) - 1;
    const d = parseInt(parts[2], 10);
    const dt = new Date(y, m, d);
    if (!isNaN(dt.getTime())) {
      const monthNames = [
        'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
      ];
      return `Next due: ${d} ${monthNames[m]}`;
    }
  }
  return `Next due: ${nearestDueDateStr}`;
}

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [data, setData] = useState(null);
  const [selectedCurrency, setSelectedCurrency] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState('');

  const fetchDashboard = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage('');
    try {
      const res = await getDashboardAnalytics();
      setData(res);
      if (res.currency && !selectedCurrency) {
        setSelectedCurrency(res.currency);
      }
    } catch (err) {
      setErrorMessage(err.message || 'Failed to load dashboard overview.');
    } finally {
      setIsLoading(false);
    }
  }, [selectedCurrency]);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] text-slate-500">
        <Loader2 className="w-8 h-8 animate-spin text-teal-600 mb-2" />
        <p className="text-sm font-medium">Loading live overview...</p>
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

  // Exact 4 metrics from database
  const total_invoiced_amount = activeCurrencyData.total_invoiced_amount ?? (data?.total_invoiced_amount || '0.00');
  const total_invoices_count = activeCurrencyData.total_invoices_count ?? (data?.total_invoices_count || 0);
  const mismatches_count = data?.mismatches_count ?? 0;
  const upcoming_due_dates_count = data?.upcoming_due_dates_count ?? 0;
  const nearest_due_date = data?.nearest_due_date;
  const recent_invoices = data?.recent_invoices || [];

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-8">
      {/* Page Header with 2 Quick-Action Buttons */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Dashboard</h1>
          <p className="text-sm text-slate-500 mt-1">
            Welcome back, <span className="font-semibold text-slate-800">{user?.name}</span>. Invoice verification, mismatch detection, and ledger overview.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => navigate('/invoices')}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-md text-xs font-semibold transition-colors shadow-xs"
          >
            <Upload className="w-3.5 h-3.5" />
            <span>Upload Invoice</span>
          </button>
          <button
            onClick={() => navigate('/reports')}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 rounded-md text-xs font-semibold transition-colors shadow-xs"
          >
            <BarChart3 className="w-3.5 h-3.5 text-teal-600" />
            <span>View Reports</span>
          </button>
        </div>
      </div>

      {/* Multi-currency Switcher (only shown when multiple currencies are detected) */}
      {data?.has_multiple_currencies && data?.by_currency && Object.keys(data.by_currency).length > 1 && (
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 text-xs text-slate-700 shadow-xs">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-slate-900">Multi-Currency Invoices:</span>
            <span>Expenses are segregated by currency to ensure financial integrity.</span>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            <span className="text-slate-500 font-medium">Currency:</span>
            {Object.keys(data.by_currency).map((curr) => (
              <button
                key={curr}
                type="button"
                onClick={() => setSelectedCurrency(curr)}
                className={`px-2.5 py-1 rounded text-xs font-semibold transition-colors ${
                  activeCurrency === curr
                    ? 'bg-teal-700 text-white shadow-xs'
                    : 'bg-white text-slate-700 hover:bg-slate-100 border border-slate-300'
                }`}
              >
                {curr}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Exactly 4 Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Total Invoice Expenses */}
        <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-xs">
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
          <p className="mt-1 text-xs text-slate-500 font-medium">
            Currency: <span className="font-bold text-slate-700">{activeCurrency}</span>
          </p>
        </div>

        {/* Card 2: Total Invoices */}
        <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500">Total Invoices</span>
            <div className="w-8 h-8 rounded-full bg-slate-100 text-slate-700 flex items-center justify-center">
              <FileCheck className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2.5">
            <span className="text-2xl font-bold text-slate-900">{total_invoices_count}</span>
          </div>
          <p className="mt-1 text-xs text-slate-500">Unique invoices processed</p>
        </div>

        {/* Card 3: Mismatches Found (Clickable) */}
        <div
          onClick={() => navigate('/invoices?status=MISMATCH')}
          className="group bg-white border border-amber-200 hover:border-amber-400 hover:shadow-md rounded-lg p-4 shadow-xs cursor-pointer transition-all duration-150"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-600 group-hover:text-amber-900 transition-colors">
              Mismatches Found
            </span>
            <div className="w-8 h-8 rounded-full bg-amber-50 text-amber-700 flex items-center justify-center group-hover:bg-amber-100 transition-colors">
              <AlertTriangle className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2.5 flex items-baseline justify-between">
            <span className="text-2xl font-extrabold text-amber-800">{mismatches_count}</span>
            <span className="text-[11px] font-semibold text-amber-700 group-hover:underline inline-flex items-center">
              View &rarr;
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-500">Invoices & records with discrepancies</p>
        </div>

        {/* Card 4: Upcoming Due Dates (Reminder only, zero payment inference) */}
        <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500">Upcoming Due Dates</span>
            <div className="w-8 h-8 rounded-full bg-sky-50 text-sky-700 flex items-center justify-center">
              <Clock className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2.5">
            <span className="text-xl font-bold text-slate-900 block truncate">
              {formatNearestDueDate(nearest_due_date, upcoming_due_dates_count)}
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            {upcoming_due_dates_count > 0
              ? `${upcoming_due_dates_count} invoice${upcoming_due_dates_count === 1 ? '' : 's'} due soon`
              : 'All current invoices are up to date'}
          </p>
        </div>
      </div>

      {/* Small Recent Activity Section (Latest 3 to 5 invoices) */}
      <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-xs">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <div>
            <h2 className="text-sm font-bold text-slate-900">Recent Activity</h2>
            <p className="text-xs text-slate-500">Latest processed invoices</p>
          </div>
          <button
            onClick={() => navigate('/invoices')}
            className="text-xs font-semibold text-teal-600 hover:text-teal-700 inline-flex items-center gap-1"
          >
            <span>View all invoices</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
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
          <div className="divide-y divide-slate-100 overflow-x-auto mt-2">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="text-slate-400 font-medium border-b border-slate-100">
                  <th className="py-2.5 pr-3">Invoice Number</th>
                  <th className="py-2.5 px-3">Supplier</th>
                  <th className="py-2.5 px-3 text-right">Amount</th>
                  <th className="py-2.5 pl-3 text-center">Verification Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {recent_invoices.slice(0, 5).map((inv) => {
                  const isNeedsReview = inv.verification_status === 'NEEDS_REVIEW';
                  return (
                    <tr
                      key={inv.id}
                      onClick={() => navigate('/invoices')}
                      className="hover:bg-slate-50/80 transition-colors cursor-pointer"
                    >
                      <td className="py-3 pr-3 font-semibold text-slate-900 whitespace-nowrap">
                        #{inv.invoice_number}
                      </td>
                      <td className="py-3 px-3 text-slate-700 max-w-[180px] truncate" title={inv.vendor_name}>
                        {inv.vendor_name}
                      </td>
                      <td className="py-3 px-3 text-right font-medium text-slate-900 whitespace-nowrap">
                        {formatCurrency(inv.total_amount, inv.currency)}
                      </td>
                      <td className="py-3 pl-3 text-center whitespace-nowrap">
                        {isNeedsReview ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-[11px] font-semibold bg-amber-50 text-amber-800 border border-amber-300">
                            Needs Review
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-[11px] font-semibold bg-emerald-50 text-emerald-800 border border-emerald-300">
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
    </div>
  );
}
