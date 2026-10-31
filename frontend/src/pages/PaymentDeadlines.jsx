import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CalendarClock,
  AlertCircle,
  Clock,
  Calendar,
  DollarSign,
  Search,
  CreditCard,
  CheckCircle2,
  Loader2,
  X,
  FileText,
  Building,
  ArrowRight,
  Filter,
  UploadCloud,
  Eye,
} from 'lucide-react';
import { getDeadlinesSummary, recordPayment } from '../api/payments';

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

function getRelativeDeadlineInfo(dueDateStr) {
  if (!dueDateStr) {
    return {
      label: 'No due date',
      badgeClass: 'text-slate-500 bg-slate-100 border-slate-200',
      daysDiff: null,
    };
  }

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const [y, m, d] = dueDateStr.split('-').map(Number);
  const due = new Date(y, m - 1, d);
  due.setHours(0, 0, 0, 0);

  const diffTime = due.getTime() - today.getTime();
  const diffDays = Math.round(diffTime / (1000 * 60 * 60 * 24));

  if (diffDays < 0) {
    const daysAgo = Math.abs(diffDays);
    return {
      label: daysAgo === 1 ? '1 day overdue' : `${daysAgo} days overdue`,
      badgeClass: 'text-rose-700 bg-rose-50 border-rose-200 font-medium',
      daysDiff: diffDays,
    };
  } else if (diffDays === 0) {
    return {
      label: 'Due today',
      badgeClass: 'text-amber-700 bg-amber-50 border-amber-200 font-medium',
      daysDiff: 0,
    };
  } else if (diffDays <= 7) {
    return {
      label: diffDays === 1 ? 'Due tomorrow' : `Due in ${diffDays} days`,
      badgeClass: 'text-sky-700 bg-sky-50 border-sky-200 font-medium',
      daysDiff: diffDays,
    };
  } else {
    return {
      label: `Due in ${diffDays} days`,
      badgeClass: 'text-slate-700 bg-slate-50 border-slate-200',
      daysDiff: diffDays,
    };
  }
}

function renderStatusBadge(status) {
  const s = (status || 'UNPAID').toUpperCase();
  switch (s) {
    case 'PAID_ON_TIME':
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
          Paid on Time
        </span>
      );
    case 'PAID_LATE':
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-300">
          Paid Late
        </span>
      );
    case 'PARTIALLY_PAID_OVERDUE':
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-300">
          Partially Paid — Overdue
        </span>
      );
    case 'PARTIALLY_PAID':
    case 'PARTIAL':
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
          Partially Paid
        </span>
      );
    case 'OVERDUE_UNCONFIRMED':
    case 'OVERDUE':
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
          Overdue — Payment Not Confirmed
        </span>
      );
    case 'UPCOMING_UNPAID':
    case 'DUE_SOON':
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-sky-50 text-sky-700 border border-sky-200">
          Upcoming / Unpaid
        </span>
      );
    case 'PAYMENT_UNVERIFIED':
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-purple-50 text-purple-700 border border-purple-200">
          Payment Unverified
        </span>
      );
    case 'NEEDS_REVIEW':
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
          Needs Review
        </span>
      );
    case 'PAID':
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-teal-50 text-teal-700 border border-teal-200">
          Paid
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200">
          Unpaid
        </span>
      );
  }
}

export default function PaymentDeadlines() {
  const navigate = useNavigate();
  const [data, setData] = useState({
    overdue: [],
    due_today: [],
    due_within_7_days: [],
    due_later: [],
    overdue_count: 0,
    overdue_total: '0.00',
    due_today_count: 0,
    due_today_total: '0.00',
    due_within_7_days_count: 0,
    due_within_7_days_total: '0.00',
    total_outstanding_amount: '0.00',
  });
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  // Active Tab: 'all' | 'overdue' | 'today' | '7days' | 'later'
  const [activeTab, setActiveTab] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  // Details Modal State
  const [detailsInvoice, setDetailsInvoice] = useState(null);

  // Quick Record Payment Modal
  const [payingInvoice, setPayingInvoice] = useState(null);
  const [paymentAmount, setPaymentAmount] = useState('');
  const [paymentDate, setPaymentDate] = useState(new Date().toISOString().split('T')[0]);
  const [paymentMethod, setPaymentMethod] = useState('Bank Transfer');
  const [paymentReference, setPaymentReference] = useState('');
  const [paymentNotes, setPaymentNotes] = useState('');
  const [modalError, setModalError] = useState('');
  const [isSubmittingPayment, setIsSubmittingPayment] = useState(false);

  const fetchDeadlines = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage('');
    try {
      const res = await getDeadlinesSummary();
      setData(res);
    } catch (err) {
      setErrorMessage(err.message || 'Failed to load payment deadlines.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDeadlines();
  }, [fetchDeadlines]);

  const showNotification = (msg) => {
    setSuccessMessage(msg);
    setTimeout(() => setSuccessMessage(''), 4000);
  };

  // Open Record Payment Modal for an invoice
  const handleOpenPayment = (inv) => {
    setPayingInvoice(inv);
    setPaymentAmount(inv.balance_due?.toString() || '0.00');
    setPaymentDate(new Date().toISOString().split('T')[0]);
    setPaymentMethod('Bank Transfer');
    setPaymentReference('');
    setPaymentNotes('');
    setModalError('');
  };

  const handleClosePaymentModal = () => {
    setPayingInvoice(null);
    setModalError('');
    setIsSubmittingPayment(false);
  };

  const handleSubmitPayment = async (e) => {
    e.preventDefault();
    if (!payingInvoice) return;

    const amt = parseFloat(paymentAmount);
    const balance = parseFloat(payingInvoice.balance_due);

    if (isNaN(amt) || amt <= 0) {
      setModalError('Please enter a valid payment amount greater than $0.00');
      return;
    }

    if (amt > balance + 0.0001) {
      setModalError(`Payment cannot exceed outstanding balance of ${formatCurrency(balance, payingInvoice.currency)}`);
      return;
    }

    if (!paymentDate) {
      setModalError('Payment date is required.');
      return;
    }

    setIsSubmittingPayment(true);
    setModalError('');

    try {
      await recordPayment({
        invoice_id: payingInvoice.id,
        amount: amt,
        payment_date: paymentDate,
        payment_method: paymentMethod,
        reference: paymentReference.trim() || null,
        notes: paymentNotes.trim() || null,
      });

      handleClosePaymentModal();
      showNotification(`Payment of ${formatCurrency(amt, payingInvoice.currency)} recorded successfully for Invoice #${payingInvoice.invoice_number}`);
      await fetchDeadlines();
    } catch (err) {
      setModalError(err.message || 'Failed to record payment.');
    } finally {
      setIsSubmittingPayment(false);
    }
  };

  // Aggregate invoices according to tab
  const getTabInvoices = () => {
    switch (activeTab) {
      case 'overdue':
        return data.overdue;
      case 'today':
        return data.due_today;
      case '7days':
        return data.due_within_7_days;
      case 'later':
        return data.due_later;
      case 'settled':
        return data.settled || [];
      case 'all':
      default:
        return [
          ...data.overdue,
          ...data.due_today,
          ...data.due_within_7_days,
          ...data.due_later,
        ];
    }
  };

  // Apply search filter
  const displayedInvoices = getTabInvoices().filter((inv) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase().trim();
    return (
      inv.invoice_number.toLowerCase().includes(q) ||
      inv.vendor_name.toLowerCase().includes(q)
    );
  });

  const allPendingCount =
    data.overdue.length +
    data.due_today.length +
    data.due_within_7_days.length +
    data.due_later.length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            Payment Deadlines
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Track upcoming due dates, prevent overdue penalties, and record payment settlements.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => navigate('/reconciliation')}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium text-teal-700 bg-teal-50 hover:bg-teal-100 border border-teal-200 rounded-md transition-colors shadow-2xs"
            title="Import bank statements or ledgers to verify payments"
          >
            <UploadCloud className="w-4 h-4" />
            <span>Upload Payment Evidence</span>
          </button>
          <button
            onClick={() => navigate('/reconciliation')}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 border border-slate-200 rounded-md transition-colors"
            title="View matched and mismatched bank transactions"
          >
            <CheckCircle2 className="w-4 h-4 text-slate-500" />
            <span>View Reconciliation</span>
          </button>
          <button
            onClick={() => navigate('/payments')}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium text-white bg-slate-900 hover:bg-slate-800 rounded-md transition-colors shadow-2xs"
            title="Open comprehensive Payment Tracker register"
          >
            <ArrowRight className="w-4 h-4" />
            <span>Payment Tracker</span>
          </button>
        </div>
      </div>

      {/* Notifications */}
      {errorMessage && (
        <div className="flex items-center gap-2 p-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded-md">
          <AlertCircle className="w-5 h-5 shrink-0 text-red-600" />
          <span>{errorMessage}</span>
        </div>
      )}

      {successMessage && (
        <div className="flex items-center gap-2 p-4 text-sm text-teal-800 bg-teal-50 border border-teal-200 rounded-md">
          <CheckCircle2 className="w-5 h-5 shrink-0 text-teal-600" />
          <span>{successMessage}</span>
        </div>
      )}

      {/* KPI Cards: Overdue, Due Today, Due in 7 Days, Total Outstanding */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Overdue */}
        <div className="bg-white border border-rose-200/80 rounded-lg p-5 shadow-xs transition-all hover:border-rose-300">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-rose-700 uppercase tracking-wider">
              Overdue
            </span>
            <div className="w-8 h-8 rounded-full bg-rose-50 text-rose-600 flex items-center justify-center">
              <AlertCircle className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-900">
              {data.overdue_count}
            </span>
            <span className="text-xs text-rose-600 font-medium">invoices</span>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Total:{' '}
            <span className="font-semibold text-rose-700">
              {formatCurrency(data.overdue_total)}
            </span>
          </p>
        </div>

        {/* Due Today */}
        <div className="bg-white border border-amber-200/80 rounded-lg p-5 shadow-xs transition-all hover:border-amber-300">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-amber-700 uppercase tracking-wider">
              Due Today
            </span>
            <div className="w-8 h-8 rounded-full bg-amber-50 text-amber-600 flex items-center justify-center">
              <Clock className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-900">
              {data.due_today_count}
            </span>
            <span className="text-xs text-amber-600 font-medium">invoices</span>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Total:{' '}
            <span className="font-semibold text-amber-700">
              {formatCurrency(data.due_today_total)}
            </span>
          </p>
        </div>

        {/* Due in 7 Days */}
        <div className="bg-white border border-sky-200/80 rounded-lg p-5 shadow-xs transition-all hover:border-sky-300">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-sky-700 uppercase tracking-wider">
              Due in Next 7 Days
            </span>
            <div className="w-8 h-8 rounded-full bg-sky-50 text-sky-600 flex items-center justify-center">
              <Calendar className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-900">
              {data.due_within_7_days_count}
            </span>
            <span className="text-xs text-sky-600 font-medium">invoices</span>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Total:{' '}
            <span className="font-semibold text-sky-700">
              {formatCurrency(data.due_within_7_days_total)}
            </span>
          </p>
        </div>

        {/* Total Outstanding */}
        <div className="bg-white border border-teal-200/80 rounded-lg p-5 shadow-xs transition-all hover:border-teal-300">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-teal-800 uppercase tracking-wider">
              Total Outstanding
            </span>
            <div className="w-8 h-8 rounded-full bg-teal-50 text-teal-600 flex items-center justify-center">
              <DollarSign className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-900">
              {formatCurrency(data.total_outstanding_amount)}
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Across {allPendingCount} pending invoices
          </p>
        </div>
      </div>

      {/* Main Filter & Table Card */}
      <div className="bg-white border border-slate-200 rounded-lg shadow-xs overflow-hidden">
        {/* Navigation Tabs and Search */}
        <div className="p-4 border-b border-slate-200 bg-slate-50/50 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          {/* Category Tabs */}
          <div className="flex flex-wrap items-center gap-1.5">
            <button
              onClick={() => setActiveTab('all')}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                activeTab === 'all'
                  ? 'bg-slate-900 text-white shadow-xs'
                  : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-100'
              }`}
            >
              All Pending ({allPendingCount})
            </button>
            <button
              onClick={() => setActiveTab('overdue')}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                activeTab === 'overdue'
                  ? 'bg-rose-700 text-white shadow-xs'
                  : 'bg-white border border-slate-200 text-rose-700 hover:bg-rose-50'
              }`}
            >
              Overdue ({data.overdue_count})
            </button>
            <button
              onClick={() => setActiveTab('today')}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                activeTab === 'today'
                  ? 'bg-amber-600 text-white shadow-xs'
                  : 'bg-white border border-slate-200 text-amber-700 hover:bg-amber-50'
              }`}
            >
              Due Today ({data.due_today_count})
            </button>
            <button
              onClick={() => setActiveTab('7days')}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                activeTab === '7days'
                  ? 'bg-sky-600 text-white shadow-xs'
                  : 'bg-white border border-slate-200 text-sky-700 hover:bg-sky-50'
              }`}
            >
              Next 7 Days ({data.due_within_7_days_count})
            </button>
            <button
              onClick={() => setActiveTab('later')}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                activeTab === 'later'
                  ? 'bg-slate-700 text-white shadow-xs'
                  : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-100'
              }`}
            >
              Due Later / None ({data.due_later.length})
            </button>
            <button
              onClick={() => setActiveTab('settled')}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                activeTab === 'settled'
                  ? 'bg-emerald-700 text-white shadow-xs'
                  : 'bg-white border border-slate-200 text-emerald-700 hover:bg-emerald-50'
              }`}
            >
              Settled ({data.settled?.length || data.settled_count || 0})
            </button>
          </div>

          {/* Search box */}
          <div className="relative w-full md:w-64">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search invoice or vendor..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 bg-white border border-slate-300 rounded-md text-xs text-slate-900 focus:outline-hidden focus:ring-1 focus:ring-teal-500 focus:border-teal-500 transition-colors"
            />
          </div>
        </div>

        {/* Deadlines Table */}
        {isLoading ? (
          <div className="p-12 text-center text-slate-500">
            <Loader2 className="w-8 h-8 animate-spin mx-auto text-teal-600 mb-2" />
            <p className="text-sm">Loading payment deadlines...</p>
          </div>
        ) : displayedInvoices.length === 0 ? (
          <div className="p-12 text-center">
            <div className="w-12 h-12 bg-slate-100 text-slate-400 rounded-full flex items-center justify-center mx-auto mb-3">
              <CalendarClock className="w-6 h-6" />
            </div>
            <h3 className="text-sm font-semibold text-slate-900">No invoices in this category</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
              {searchQuery
                ? 'No invoices match your search keyword. Try clearing the search query.'
                : 'All invoices in this category are fully paid or there are no pending obligations.'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-700 divide-y divide-slate-200">
              <thead className="bg-slate-50 text-xs font-semibold text-slate-600 uppercase tracking-wider">
                <tr>
                  <th className="px-6 py-3.5">Invoice #</th>
                  <th className="px-6 py-3.5">Supplier / Vendor</th>
                  <th className="px-6 py-3.5">Due Date & Urgency</th>
                  <th className="px-6 py-3.5 text-right">Invoice Total</th>
                  <th className="px-6 py-3.5 text-right">Paid to Date</th>
                  <th className="px-6 py-3.5 text-right">Balance Due</th>
                  <th className="px-6 py-3.5 text-center">Status</th>
                  <th className="px-6 py-3.5 text-center">Review & Eligibility</th>
                  <th className="px-6 py-3.5 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {displayedInvoices.map((inv) => {
                  const deadlineInfo = getRelativeDeadlineInfo(inv.due_date);
                  return (
                    <tr key={inv.id} className="hover:bg-slate-50/70 transition-colors">
                      {/* Invoice Number */}
                      <td className="px-6 py-4 font-medium text-slate-900 whitespace-nowrap">
                        {inv.invoice_number}
                      </td>

                      {/* Vendor Name */}
                      <td className="px-6 py-4 text-slate-800 whitespace-nowrap">
                        {inv.vendor_name}
                      </td>

                      {/* Due Date & Urgency Tag */}
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex flex-col gap-0.5">
                          <span className="text-xs font-medium text-slate-900">
                            {inv.due_date || (
                              <span className="text-slate-400 italic">Unspecified</span>
                            )}
                          </span>
                          <span
                            className={`inline-flex items-center px-1.5 py-0.5 rounded text-[11px] border w-fit ${deadlineInfo.badgeClass}`}
                          >
                            {deadlineInfo.label}
                          </span>
                        </div>
                      </td>

                      {/* Total Amount */}
                      <td className="px-6 py-4 text-right text-slate-600 whitespace-nowrap">
                        {formatCurrency(inv.total_amount, inv.currency)}
                      </td>

                      {/* Paid Amount */}
                      <td className="px-6 py-4 text-right text-slate-600 whitespace-nowrap">
                        {formatCurrency(inv.total_paid, inv.currency)}
                      </td>

                      {/* Outstanding Balance */}
                      <td className="px-6 py-4 text-right font-semibold text-slate-900 whitespace-nowrap">
                        {formatCurrency(inv.balance_due, inv.currency)}
                      </td>

                      {/* Status */}
                      <td className="px-6 py-4 text-center whitespace-nowrap">
                        {renderStatusBadge(inv.granular_status || inv.payment_status)}
                      </td>

                      {/* Review & Eligibility */}
                      <td className="px-6 py-4 text-center whitespace-nowrap">
                        {inv.status === 'NEEDS_REVIEW' ? (
                          <div className="flex flex-col items-center">
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-50 text-amber-800 border border-amber-200">
                              ⚠ Needs Review
                            </span>
                            <span className="text-[10px] text-amber-700 mt-0.5">
                              Eligible with caution
                            </span>
                          </div>
                        ) : (
                          <div className="flex flex-col items-center">
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                              ✓ Verified
                            </span>
                            <span className="text-[10px] text-slate-500 mt-0.5">
                              Eligible
                            </span>
                          </div>
                        )}
                      </td>

                      {/* Action */}
                      <td className="px-6 py-4 text-right whitespace-nowrap">
                        <div className="flex items-center justify-end gap-2">
                          {parseFloat(inv.balance_due) > 0.001 ? (
                            <button
                              onClick={() => handleOpenPayment(inv)}
                              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-teal-600 hover:bg-teal-700 text-white rounded text-xs font-medium transition-colors shadow-2xs"
                              title="Record payment settlement for this invoice"
                            >
                              <DollarSign className="w-3.5 h-3.5" />
                              <span>Record Payment</span>
                            </button>
                          ) : (
                            <span className="inline-flex items-center px-2.5 py-1 text-xs font-medium text-emerald-700 bg-emerald-50 rounded border border-emerald-200">
                              ✓ Settled
                            </span>
                          )}

                          <button
                            onClick={() => setDetailsInvoice(inv)}
                            className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded transition-colors"
                            title="View invoice information, due date, and verification status"
                          >
                            <Eye className="w-3.5 h-3.5" />
                            <span>View Details</span>
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

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex items-center justify-between text-xs text-slate-500">
          <span>Showing {displayedInvoices.length} invoices</span>
          <span>Due date calculations based on verified calendar records</span>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* RECORD PAYMENT MODAL                                                      */}
      {/* ========================================================================= */}
      {payingInvoice && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
          <div className="bg-white rounded-lg border border-slate-200 shadow-xl max-w-lg w-full flex flex-col overflow-hidden">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50/50">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded bg-teal-600 flex items-center justify-center text-white">
                  <CreditCard className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-base font-semibold text-slate-900">Record Payment</h3>
                  <p className="text-xs text-slate-500">
                    Settle invoice #{payingInvoice.invoice_number}
                  </p>
                </div>
              </div>
              <button
                onClick={handleClosePaymentModal}
                className="text-slate-400 hover:text-slate-600 p-1.5 rounded-md hover:bg-slate-100"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Form */}
            <form onSubmit={handleSubmitPayment} className="p-6 space-y-4">
              {modalError && (
                <div className="flex items-start gap-2 p-3 text-xs text-red-700 bg-red-50 border border-red-200 rounded-md">
                  <AlertCircle className="w-4 h-4 shrink-0 text-red-600 mt-0.5" />
                  <span>{modalError}</span>
                </div>
              )}

              {payingInvoice.status === 'NEEDS_REVIEW' && (
                <div className="p-3 bg-amber-50 border border-amber-200 rounded-md text-xs text-amber-900 leading-relaxed">
                  <strong>Notice:</strong> This invoice has validation discrepancies and is marked as <em>Needs Review</em>. Payment recording is permitted, but please verify figures before recording settlement.
                </div>
              )}

              <div className="p-3 bg-blue-50 border border-blue-200 rounded-md text-xs text-blue-900 leading-relaxed">
                <strong>Audit Notice:</strong> Manual payment entries default to <em>Unverified Claim</em> status. To officially verify this payment and clear it against bank debit records, upload a bank statement in the Reconciliation Centre.
              </div>

              {/* Invoice Summary Box */}
              <div className="p-3 bg-slate-50 rounded-md border border-slate-200 text-xs space-y-1.5">
                <div className="flex justify-between text-slate-600">
                  <span>Vendor:</span>
                  <span className="font-medium text-slate-800">{payingInvoice.vendor_name}</span>
                </div>
                <div className="flex justify-between text-slate-600">
                  <span>Invoice Total:</span>
                  <span className="font-medium text-slate-800">
                    {formatCurrency(payingInvoice.total_amount, payingInvoice.currency)}
                  </span>
                </div>
                <div className="flex justify-between text-slate-600">
                  <span>Already Paid:</span>
                  <span className="font-medium text-slate-800">
                    {formatCurrency(payingInvoice.total_paid, payingInvoice.currency)}
                  </span>
                </div>
                <div className="flex justify-between border-t border-slate-200 pt-1.5 text-slate-900 font-semibold">
                  <span>Remaining Balance:</span>
                  <span className="text-teal-700 font-bold">
                    {formatCurrency(payingInvoice.balance_due, payingInvoice.currency)}
                  </span>
                </div>
              </div>

              {/* Amount and Date */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Payment Amount *
                  </label>
                  <div className="relative">
                    <DollarSign className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                    <input
                      type="number"
                      step="0.01"
                      min="0.01"
                      max={payingInvoice.balance_due}
                      required
                      value={paymentAmount}
                      onChange={(e) => setPaymentAmount(e.target.value)}
                      className="w-full pl-8 pr-3 py-2 bg-white border border-slate-300 rounded-md text-sm text-slate-900 focus:outline-hidden focus:ring-1 focus:ring-teal-500 focus:border-teal-500"
                    />
                  </div>
                  <span className="text-[11px] text-slate-400 mt-1 block">
                    Pre-filled with exact balance
                  </span>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Payment Date *
                  </label>
                  <input
                    type="date"
                    required
                    value={paymentDate}
                    onChange={(e) => setPaymentDate(e.target.value)}
                    className="w-full px-3 py-2 bg-white border border-slate-300 rounded-md text-sm text-slate-900 focus:outline-hidden focus:ring-1 focus:ring-teal-500 focus:border-teal-500"
                  />
                </div>
              </div>

              {/* Method & Reference */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Payment Method *
                  </label>
                  <select
                    value={paymentMethod}
                    onChange={(e) => setPaymentMethod(e.target.value)}
                    className="w-full px-3 py-2 bg-white border border-slate-300 rounded-md text-sm text-slate-900 focus:outline-hidden focus:ring-1 focus:ring-teal-500 focus:border-teal-500"
                  >
                    <option value="Bank Transfer">Bank Transfer</option>
                    <option value="Credit Card">Credit Card</option>
                    <option value="Debit Card">Debit Card</option>
                    <option value="Cash">Cash</option>
                    <option value="Cheque">Cheque</option>
                    <option value="UPI">UPI</option>
                    <option value="Other">Other</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Transaction / Reference ID
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. TXN-94812"
                    value={paymentReference}
                    onChange={(e) => setPaymentReference(e.target.value)}
                    className="w-full px-3 py-2 bg-white border border-slate-300 rounded-md text-sm text-slate-900 focus:outline-hidden focus:ring-1 focus:ring-teal-500 focus:border-teal-500"
                  />
                </div>
              </div>

              {/* Notes */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Notes (Optional)
                </label>
                <textarea
                  rows={2}
                  placeholder="Additional payment details or remarks..."
                  value={paymentNotes}
                  onChange={(e) => setPaymentNotes(e.target.value)}
                  className="w-full px-3 py-2 bg-white border border-slate-300 rounded-md text-sm text-slate-900 focus:outline-hidden focus:ring-1 focus:ring-teal-500 focus:border-teal-500"
                />
              </div>

              {/* Actions */}
              <div className="pt-3 border-t border-slate-200 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={handleClosePaymentModal}
                  className="px-4 py-2 border border-slate-300 hover:bg-slate-50 text-slate-700 rounded-md text-xs font-medium transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmittingPayment}
                  className="inline-flex items-center gap-1.5 px-4 py-2 bg-teal-600 hover:bg-teal-700 disabled:opacity-50 text-white rounded-md text-xs font-medium transition-colors shadow-xs"
                >
                  {isSubmittingPayment && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>Record Payment</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* VIEW INVOICE DETAILS & VERIFICATION MODAL                                */}
      {/* ========================================================================= */}
      {detailsInvoice && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
          <div className="bg-white rounded-lg border border-slate-200 shadow-xl max-w-xl w-full flex flex-col overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50/70">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded bg-slate-100 flex items-center justify-center text-slate-700">
                  <FileText className="w-4 h-4 text-teal-700" />
                </div>
                <div>
                  <h3 className="text-base font-semibold text-slate-900">
                    Invoice #{detailsInvoice.invoice_number}
                  </h3>
                  <p className="text-xs text-slate-500">{detailsInvoice.vendor_name}</p>
                </div>
              </div>
              <button
                onClick={() => setDetailsInvoice(null)}
                className="text-slate-400 hover:text-slate-600 p-1.5 rounded-md hover:bg-slate-100"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              {/* Financial Breakdown Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-3 bg-slate-50 border border-slate-200 rounded-md text-center">
                <div>
                  <span className="text-2xs text-slate-500 uppercase font-semibold">Total Amount</span>
                  <p className="text-sm font-bold text-slate-900">
                    {formatCurrency(detailsInvoice.total_amount, detailsInvoice.currency)}
                  </p>
                </div>
                <div>
                  <span className="text-2xs text-slate-500 uppercase font-semibold">Verified Paid</span>
                  <p className="text-sm font-bold text-emerald-700">
                    {formatCurrency(detailsInvoice.verified_paid || detailsInvoice.total_paid || 0, detailsInvoice.currency)}
                  </p>
                </div>
                <div>
                  <span className="text-2xs text-slate-500 uppercase font-semibold">Unverified Claims</span>
                  <p className="text-sm font-bold text-amber-700">
                    {formatCurrency(detailsInvoice.unverified_paid || 0, detailsInvoice.currency)}
                  </p>
                </div>
                <div>
                  <span className="text-2xs text-slate-500 uppercase font-semibold">Outstanding Balance</span>
                  <p className="text-sm font-bold text-rose-700">
                    {formatCurrency(detailsInvoice.balance_due, detailsInvoice.currency)}
                  </p>
                </div>
              </div>

              {/* Status and Timing Details */}
              <div className="space-y-2 text-xs border border-slate-200 rounded-md p-3.5 bg-white">
                <div className="flex justify-between items-center py-1 border-b border-slate-100">
                  <span className="text-slate-500">Current Payment Status:</span>
                  <div>{renderStatusBadge(detailsInvoice.payment_status)}</div>
                </div>
                <div className="flex justify-between items-center py-1 border-b border-slate-100">
                  <span className="text-slate-500">Invoice Date:</span>
                  <span className="font-medium text-slate-800">{detailsInvoice.invoice_date || '—'}</span>
                </div>
                <div className="flex justify-between items-center py-1 border-b border-slate-100">
                  <span className="text-slate-500">Due Date:</span>
                  <span className="font-medium text-slate-800">{detailsInvoice.due_date || '—'}</span>
                </div>
                <div className="flex justify-between items-center py-1 border-b border-slate-100">
                  <span className="text-slate-500">Timing Assessment:</span>
                  <span className="font-medium text-slate-800">
                    {detailsInvoice.days_late != null && detailsInvoice.days_late > 0
                      ? `Paid ${detailsInvoice.days_late} day${detailsInvoice.days_late === 1 ? '' : 's'} late`
                      : detailsInvoice.days_overdue != null && detailsInvoice.days_overdue > 0
                      ? `${detailsInvoice.days_overdue} day${detailsInvoice.days_overdue === 1 ? '' : 's'} overdue`
                      : detailsInvoice.days_remaining != null
                      ? `Due in ${detailsInvoice.days_remaining} day${detailsInvoice.days_remaining === 1 ? '' : 's'}`
                      : 'On schedule'}
                  </span>
                </div>
                <div className="flex justify-between items-center py-1 border-b border-slate-100">
                  <span className="text-slate-500">Verification Source:</span>
                  <span className="font-medium text-slate-800">
                    {detailsInvoice.evidence_source || 'Evidence Unavailable (Manual Claim)'}
                  </span>
                </div>
                {detailsInvoice.matched_reference && (
                  <div className="flex justify-between items-center py-1 border-b border-slate-100">
                    <span className="text-slate-500">Matched Bank / Ledger Ref:</span>
                    <span className="font-mono font-medium text-slate-800">{detailsInvoice.matched_reference}</span>
                  </div>
                )}
                {detailsInvoice.mismatch_reason && (
                  <div className="flex justify-between items-center py-1 border-b border-slate-100">
                    <span className="text-slate-500">Mismatch Reason:</span>
                    <span className="text-rose-700 font-medium">{detailsInvoice.mismatch_reason}</span>
                  </div>
                )}
              </div>

              {/* Action Buttons in Modal */}
              <div className="pt-3 border-t border-slate-200 flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      const inv = detailsInvoice;
                      setDetailsInvoice(null);
                      navigate('/reconciliation');
                    }}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-teal-700 bg-teal-50 hover:bg-teal-100 border border-teal-200 rounded-md transition-colors"
                  >
                    <UploadCloud className="w-3.5 h-3.5" />
                    <span>Upload Evidence</span>
                  </button>
                  <button
                    onClick={() => {
                      setDetailsInvoice(null);
                      navigate('/reconciliation');
                    }}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-md transition-colors"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5 text-slate-500" />
                    <span>View Reconciliation</span>
                  </button>
                </div>

                <div className="flex items-center gap-2">
                  {parseFloat(detailsInvoice.balance_due) > 0.001 && (
                    <button
                      onClick={() => {
                        const inv = detailsInvoice;
                        setDetailsInvoice(null);
                        handleOpenPayment(inv);
                      }}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-teal-600 hover:bg-teal-700 text-white rounded-md text-xs font-medium transition-colors shadow-2xs"
                    >
                      <DollarSign className="w-3.5 h-3.5" />
                      <span>Record Payment</span>
                    </button>
                  )}
                  <button
                    onClick={() => setDetailsInvoice(null)}
                    className="px-3.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100 rounded-md"
                  >
                    Close
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
