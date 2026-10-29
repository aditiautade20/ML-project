import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  DollarSign,
  FileText,
  CreditCard,
  AlertCircle,
  Calendar,
  Clock,
  Sparkles,
  ArrowRight,
  TrendingUp,
  Loader2,
  CheckCircle2,
  Building,
  Upload,
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
      setErrorMessage(err.message || 'Failed to load dashboard metrics.');
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
        <p className="text-sm font-medium">Loading live dashboard metrics...</p>
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

  const total_invoices_count = activeCurrencyData.total_invoices_count ?? (data?.total_invoices_count || 0);
  const total_invoiced_amount = activeCurrencyData.total_invoiced_amount ?? (data?.total_invoiced_amount || '0.00');
  const total_paid_amount = activeCurrencyData.total_paid_amount ?? (data?.total_paid_amount || '0.00');
  const total_outstanding_balance = activeCurrencyData.total_outstanding_balance ?? (data?.total_outstanding_balance || '0.00');
  const overdue_count = activeCurrencyData.overdue_count ?? (data?.overdue_count || 0);
  const overdue_amount = activeCurrencyData.overdue_amount ?? (data?.overdue_amount || '0.00');
  const due_within_7_days_count = activeCurrencyData.due_within_7_days_count ?? (data?.due_within_7_days_count || 0);
  const due_within_7_days_amount = activeCurrencyData.due_within_7_days_amount ?? (data?.due_within_7_days_amount || '0.00');
  const anomalous_invoices_count = data?.anomalous_invoices_count || 0;
  const status_counts = activeCurrencyData.status_counts || data?.status_counts || {
    PAID: 0,
    PARTIAL: 0,
    UNPAID: 0,
    DUE_SOON: 0,
    OVERDUE: 0,
  };
  const monthly_trends = data?.monthly_trends || [];
  const recent_invoices = data?.recent_invoices || [];
  const recent_payments = data?.recent_payments || [];

  const invoicedNum = parseFloat(total_invoiced_amount);
  const paidNum = parseFloat(total_paid_amount);
  const paidPercentage = invoicedNum > 0 ? Math.min(100, (paidNum / invoicedNum) * 100) : 0;

  // Maximum value for scaling the bar chart
  const maxTrendValue = Math.max(
    1,
    ...monthly_trends.map((t) =>
      Math.max(parseFloat(t.invoiced_amount || 0), parseFloat(t.paid_amount || 0))
    )
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Dashboard</h1>
          <p className="text-sm text-slate-500 mt-1">
            Welcome back, <span className="font-semibold text-slate-800">{user?.name}</span>. Here is your financial overview.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate('/invoices')}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-md text-xs font-medium transition-colors shadow-xs"
          >
            <Upload className="w-3.5 h-3.5" />
            <span>Upload Invoice</span>
          </button>
          <button
            onClick={() => navigate('/payments')}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 rounded-md text-xs font-medium transition-colors shadow-xs"
          >
            <CreditCard className="w-3.5 h-3.5" />
            <span>Record Payment</span>
          </button>
        </div>
      </div>

      {/* Multi-currency Switcher Banner */}
      {data?.has_multiple_currencies && data?.by_currency && Object.keys(data.by_currency).length > 1 && (
        <div className="bg-amber-50/90 border border-amber-200 rounded-lg p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-amber-950 shadow-xs">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-amber-900">Multi-Currency Portfolio:</span>
            <span>Metrics are segmented by currency to prevent cross-currency summation errors.</span>
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

      {/* Top KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        {/* Total Invoiced */}
        <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
              Total Invoiced
            </span>
            <div className="w-7 h-7 rounded-full bg-slate-100 text-slate-600 flex items-center justify-center">
              <FileText className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="mt-2">
            <span className="text-xl font-bold text-slate-900">
              {formatCurrency(total_invoiced_amount, activeCurrency)}
            </span>
          </div>
          <p className="mt-1 text-[11px] text-slate-500">
            Across {total_invoices_count} invoices ({activeCurrency})
          </p>
        </div>

        {/* Total Paid */}
        <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
              Total Paid
            </span>
            <div className="w-7 h-7 rounded-full bg-teal-50 text-teal-600 flex items-center justify-center">
              <CheckCircle2 className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="mt-2">
            <span className="text-xl font-bold text-teal-700">
              {formatCurrency(total_paid_amount, activeCurrency)}
            </span>
          </div>
          <div className="mt-1 flex items-center gap-1.5 text-[11px] text-slate-500">
            <div className="flex-1 bg-slate-100 rounded-full h-1.5 overflow-hidden">
              <div
                className="bg-teal-600 h-1.5 rounded-full"
                style={{ width: `${paidPercentage}%` }}
              />
            </div>
            <span>{paidPercentage.toFixed(0)}%</span>
          </div>
        </div>

        {/* Outstanding Balance */}
        <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
              Outstanding
            </span>
            <div className="w-7 h-7 rounded-full bg-slate-100 text-slate-700 flex items-center justify-center">
              <DollarSign className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="mt-2">
            <span className="text-xl font-bold text-slate-900">
              {formatCurrency(total_outstanding_balance, activeCurrency)}
            </span>
          </div>
          <p className="mt-1 text-[11px] text-slate-500">Pending settlement ({activeCurrency})</p>
        </div>

        {/* Overdue */}
        <div className="bg-white border border-rose-200/80 rounded-lg p-4 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-rose-700 uppercase tracking-wider">
              Overdue
            </span>
            <div className="w-7 h-7 rounded-full bg-rose-50 text-rose-600 flex items-center justify-center">
              <AlertCircle className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="mt-2 flex items-baseline gap-1.5">
            <span className="text-xl font-bold text-slate-900">{overdue_count}</span>
            <span className="text-xs text-rose-600 font-medium">invoices</span>
          </div>
          <p className="mt-1 text-[11px] font-semibold text-rose-700">
            {formatCurrency(overdue_amount, activeCurrency)}
          </p>
        </div>

        {/* Due in 7 Days */}
        <div className="bg-white border border-sky-200/80 rounded-lg p-4 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-sky-700 uppercase tracking-wider">
              Due in 7 Days
            </span>
            <div className="w-7 h-7 rounded-full bg-sky-50 text-sky-600 flex items-center justify-center">
              <Clock className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="mt-2 flex items-baseline gap-1.5">
            <span className="text-xl font-bold text-slate-900">{due_within_7_days_count}</span>
            <span className="text-xs text-sky-600 font-medium">invoices</span>
          </div>
          <p className="mt-1 text-[11px] font-semibold text-sky-700">
            {formatCurrency(due_within_7_days_amount, activeCurrency)}
          </p>
        </div>

        {/* ML Anomaly Flag */}
        <div
          onClick={() => navigate('/anomalies')}
          className="bg-white border border-slate-200 hover:border-teal-300 rounded-lg p-4 shadow-xs cursor-pointer transition-colors"
        >
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
              ML Anomalies
            </span>
            <div className="w-7 h-7 rounded-full bg-teal-50 text-teal-600 flex items-center justify-center">
              <Sparkles className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="mt-2 flex items-baseline gap-1.5">
            <span className="text-xl font-bold text-slate-900">
              {anomalous_invoices_count}
            </span>
            <span className="text-xs text-slate-500 font-medium">flagged</span>
          </div>
          <p className="mt-1 text-[11px] text-teal-700 hover:underline flex items-center gap-1 font-medium">
            <span>Review screening</span>
            <ArrowRight className="w-3 h-3" />
          </p>
        </div>
      </div>

      {/* Invoice Status Distribution Strip */}
      <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-2.5">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
              Invoice Status Breakdown
            </span>
            <span className="text-xs text-slate-400">({total_invoices_count} total invoices)</span>
          </div>
          <Link
            to="/invoices"
            className="text-xs text-teal-700 hover:text-teal-800 font-medium inline-flex items-center gap-1"
          >
            <span>View All Invoices</span>
            <ArrowRight className="w-3 h-3" />
          </Link>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5">
          <div className="bg-teal-50/60 border border-teal-200/80 rounded-md p-2.5">
            <span className="text-[11px] font-medium text-teal-800">Fully Paid</span>
            <p className="text-base font-bold text-teal-900 mt-0.5">{status_counts.PAID || 0}</p>
          </div>
          <div className="bg-amber-50/60 border border-amber-200/80 rounded-md p-2.5">
            <span className="text-[11px] font-medium text-amber-800">Partially Paid</span>
            <p className="text-base font-bold text-amber-900 mt-0.5">{status_counts.PARTIAL || 0}</p>
          </div>
          <div className="bg-sky-50/60 border border-sky-200/80 rounded-md p-2.5">
            <span className="text-[11px] font-medium text-sky-800">Due Soon (&le; 7d)</span>
            <p className="text-base font-bold text-sky-900 mt-0.5">{status_counts.DUE_SOON || 0}</p>
          </div>
          <div className="bg-slate-50 border border-slate-200 rounded-md p-2.5">
            <span className="text-[11px] font-medium text-slate-700">Unpaid</span>
            <p className="text-base font-bold text-slate-900 mt-0.5">{status_counts.UNPAID || 0}</p>
          </div>
          <div className="bg-rose-50/60 border border-rose-200/80 rounded-md p-2.5">
            <span className="text-[11px] font-medium text-rose-800">Overdue</span>
            <p className="text-base font-bold text-rose-900 mt-0.5">{status_counts.OVERDUE || 0}</p>
          </div>
        </div>
      </div>

      {/* Monthly Invoiced vs Paid Trends Chart */}
      <div className="bg-white border border-slate-200 rounded-lg p-6 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-6">
          <div>
            <h2 className="text-base font-semibold text-slate-900">Monthly Cash Flow Trends</h2>
            <p className="text-xs text-slate-500">
              Historical monthly comparison of total invoiced commitments vs recorded payments
            </p>
          </div>

          {/* Legend */}
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

        {/* Bar Chart Visualization */}
        <div className="grid grid-cols-6 gap-3 sm:gap-6 pt-6 pb-2 border-b border-slate-100">
          {monthly_trends.map((m) => {
            const invVal = parseFloat(m.invoiced_amount || 0);
            const paidVal = parseFloat(m.paid_amount || 0);
            const invHeight = Math.max(4, Math.round((invVal / maxTrendValue) * 120));
            const paidHeight = Math.max(4, Math.round((paidVal / maxTrendValue) * 120));

            return (
              <div key={m.month_key} className="flex flex-col items-center">
                {/* Dual Bars */}
                <div className="h-32 flex items-end justify-center gap-1.5 w-full">
                  {/* Invoiced Bar */}
                  <div className="relative group flex flex-col items-center w-4 sm:w-6">
                    <div
                      className="w-full bg-teal-600 hover:bg-teal-700 rounded-t-xs transition-all duration-300"
                      style={{ height: `${invHeight}px` }}
                    />
                    {/* Hover tooltip */}
                    <div className="absolute bottom-full mb-1 hidden group-hover:block z-10 px-2 py-1 bg-slate-900 text-white text-[10px] rounded whitespace-nowrap shadow-md">
                      Invoiced: {formatCurrency(invVal)}
                    </div>
                  </div>

                  {/* Paid Bar */}
                  <div className="relative group flex flex-col items-center w-4 sm:w-6">
                    <div
                      className="w-full bg-slate-400 hover:bg-slate-500 rounded-t-xs transition-all duration-300"
                      style={{ height: `${paidHeight}px` }}
                    />
                    {/* Hover tooltip */}
                    <div className="absolute bottom-full mb-1 hidden group-hover:block z-10 px-2 py-1 bg-slate-900 text-white text-[10px] rounded whitespace-nowrap shadow-md">
                      Paid: {formatCurrency(paidVal)}
                    </div>
                  </div>
                </div>

                {/* Month Label */}
                <span className="text-[11px] font-medium text-slate-600 mt-2 text-center whitespace-nowrap">
                  {m.month_label}
                </span>
                <span className="text-[10px] text-slate-400">
                  {formatCurrency(invVal)}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Split Bottom Row: Recent Invoices & Recent Payments */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Invoices Card */}
        <div className="bg-white border border-slate-200 rounded-lg shadow-xs overflow-hidden flex flex-col">
          <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50/50">
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-teal-600" />
              <h3 className="text-sm font-semibold text-slate-900">Recent Invoices</h3>
            </div>
            <Link
              to="/invoices"
              className="text-xs text-teal-700 hover:text-teal-800 font-medium inline-flex items-center gap-1"
            >
              <span>View All</span>
              <ArrowRight className="w-3 h-3" />
            </Link>
          </div>

          <div className="p-0 flex-1">
            {recent_invoices.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500">
                No invoices uploaded yet.
              </div>
            ) : (
              <div className="divide-y divide-slate-100">
                {recent_invoices.map((inv) => (
                  <div
                    key={inv.id}
                    className="px-5 py-3 hover:bg-slate-50/70 transition-colors flex items-center justify-between text-xs"
                  >
                    <div>
                      <div className="font-semibold text-slate-900">{inv.invoice_number}</div>
                      <div className="text-slate-500 text-[11px]">{inv.vendor_name} &bull; {inv.invoice_date}</div>
                    </div>
                    <div className="text-right">
                      <div className="font-semibold text-slate-900">
                        {formatCurrency(inv.total_amount, inv.currency)}
                      </div>
                      <div className="text-[11px]">
                        {inv.payment_status === 'PAID' ? (
                          <span className="text-teal-700 font-medium">Fully Paid</span>
                        ) : inv.payment_status === 'OVERDUE' ? (
                          <span className="text-rose-600 font-medium">Overdue</span>
                        ) : (
                          <span className="text-slate-500">Due: {formatCurrency(inv.balance_due, inv.currency)}</span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Recent Payments Card */}
        <div className="bg-white border border-slate-200 rounded-lg shadow-xs overflow-hidden flex flex-col">
          <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50/50">
            <div className="flex items-center gap-2">
              <CreditCard className="w-4 h-4 text-teal-600" />
              <h3 className="text-sm font-semibold text-slate-900">Recent Payments</h3>
            </div>
            <Link
              to="/payments"
              className="text-xs text-teal-700 hover:text-teal-800 font-medium inline-flex items-center gap-1"
            >
              <span>View All</span>
              <ArrowRight className="w-3 h-3" />
            </Link>
          </div>

          <div className="p-0 flex-1">
            {recent_payments.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500">
                No payments recorded yet.
              </div>
            ) : (
              <div className="divide-y divide-slate-100">
                {recent_payments.map((p) => (
                  <div
                    key={p.id}
                    className="px-5 py-3 hover:bg-slate-50/70 transition-colors flex items-center justify-between text-xs"
                  >
                    <div>
                      <div className="font-semibold text-slate-900">{p.vendor_name}</div>
                      <div className="text-slate-500 text-[11px]">
                        Inv #{p.invoice_number} &bull; {p.payment_method}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-bold text-teal-700">
                        {formatCurrency(p.amount, p.currency || activeCurrency)}
                      </div>
                      <div className="text-[11px] text-slate-400">{p.payment_date}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
