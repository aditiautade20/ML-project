import React, { useState, useEffect, useCallback } from 'react';
import {
  CreditCard,
  Plus,
  Search,
  Trash2,
  Edit2,
  AlertCircle,
  CheckCircle2,
  Loader2,
  X,
  DollarSign,
  Calendar,
  FileText,
  Building,
  Clock,
  History,
  AlertTriangle,
  ArrowRight,
  Filter,
} from 'lucide-react';
import {
  getPayments,
  recordPayment,
  updatePayment,
  deletePayment,
  getInvoicePaymentSummary,
} from '../api/payments';
import { getInvoices } from '../api/invoices';

export default function PaymentTracker() {
  // Navigation Tab: 'invoices' (Invoice Balances & Tracking) or 'transactions' (Payment Transaction Log)
  const [activeTab, setActiveTab] = useState('invoices');

  // Invoices Register State
  const [invoices, setInvoices] = useState([]);
  const [isLoadingInvoices, setIsLoadingInvoices] = useState(true);
  const [invoiceSearchQuery, setInvoiceSearchQuery] = useState('');
  const [invoiceStatusFilter, setInvoiceStatusFilter] = useState('ALL');
  const [invoicePage, setInvoicePage] = useState(1);
  const [invoiceTotalCount, setInvoiceTotalCount] = useState(0);

  // Payments State
  const [payments, setPayments] = useState([]);
  const [totalPaymentsCount, setTotalPaymentsCount] = useState(0);
  const [totalRecordedAmount, setTotalRecordedAmount] = useState('0.00');
  const [isLoadingPayments, setIsLoadingPayments] = useState(true);
  const [paymentSearchQuery, setPaymentSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('payment_date');
  const [sortOrder, setSortOrder] = useState('desc');
  const [paymentPage, setPaymentPage] = useState(1);
  const perPage = 20;

  // Global Messages
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  // Dropdown list for payment modal
  const [allAvailableInvoices, setAllAvailableInvoices] = useState([]);

  // Record Payment Modal State
  const [showRecordModal, setShowRecordModal] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState('');
  const [selectedInvoice, setSelectedInvoice] = useState(null);
  const [newPayment, setNewPayment] = useState({
    invoice_id: '',
    amount: '',
    payment_date: new Date().toISOString().split('T')[0],
    payment_method: 'Bank Transfer',
    reference: '',
    notes: '',
  });

  // Invoice History Modal State
  const [historyInvoice, setHistoryInvoice] = useState(null);
  const [historySummary, setHistorySummary] = useState(null);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);

  // Edit Payment Modal State
  const [editingPayment, setEditingPayment] = useState(null);
  const [isUpdating, setIsUpdating] = useState(false);
  const [editError, setEditError] = useState('');

  // Delete Payment Modal State
  const [deletingPayment, setDeletingPayment] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const showNotification = (msg) => {
    setSuccessMessage(msg);
    setTimeout(() => setSuccessMessage(''), 4500);
  };

  // 1. Fetch Invoices Register (Source of truth)
  const fetchInvoicesList = useCallback(async () => {
    setIsLoadingInvoices(true);
    try {
      const params = {
        page: invoicePage,
        per_page: 50,
      };
      if (invoiceSearchQuery.trim()) {
        params.search = invoiceSearchQuery.trim();
      }
      if (invoiceStatusFilter && invoiceStatusFilter !== 'ALL') {
        params.payment_status = invoiceStatusFilter;
      }
      const res = await getInvoices(params);
      setInvoices(res.items || []);
      setInvoiceTotalCount(res.total || 0);
    } catch (err) {
      setErrorMessage(err.message || 'Failed to load invoices.');
    } finally {
      setIsLoadingInvoices(false);
    }
  }, [invoiceSearchQuery, invoiceStatusFilter, invoicePage]);

  // 2. Fetch Payments Transactions
  const fetchPaymentsList = useCallback(async () => {
    setIsLoadingPayments(true);
    try {
      const res = await getPayments({
        search: paymentSearchQuery.trim(),
        sort_by: sortBy,
        sort_order: sortOrder,
        page: paymentPage,
        per_page: perPage,
      });
      setPayments(res.items || []);
      setTotalPaymentsCount(res.total || 0);
      setTotalRecordedAmount(res.total_amount_recorded || '0.00');
    } catch (err) {
      setErrorMessage(err.message || 'Failed to load payments.');
    } finally {
      setIsLoadingPayments(false);
    }
  }, [paymentSearchQuery, sortBy, sortOrder, paymentPage]);

  // 3. Fetch all active invoices for modal dropdown
  const loadInvoicesForDropdown = async () => {
    try {
      const res = await getInvoices({ per_page: 100 });
      setAllAvailableInvoices(res.items || []);
    } catch (err) {
      console.error('Failed to load eligible invoices for dropdown:', err);
    }
  };

  useEffect(() => {
    fetchInvoicesList();
  }, [fetchInvoicesList]);

  useEffect(() => {
    fetchPaymentsList();
  }, [fetchPaymentsList]);

  // Calculate Aggregates for KPI Cards
  const kpiTotalInvoiced = invoices.reduce((acc, inv) => acc + (parseFloat(inv.total_amount) || 0), 0);
  const kpiTotalPaid = invoices.reduce((acc, inv) => acc + (parseFloat(inv.amount_paid) || 0), 0);
  const kpiOutstanding = invoices.reduce((acc, inv) => acc + (parseFloat(inv.balance_due) || 0), 0);
  const kpiPaidCount = invoices.filter((inv) => (parseFloat(inv.balance_due) || 0) <= 0.001).length;

  // Open Record Payment Modal
  const handleOpenRecordModal = (preselectedInvoice = null) => {
    setFormError('');
    setSelectedInvoice(preselectedInvoice || null);
    setNewPayment({
      invoice_id: preselectedInvoice ? preselectedInvoice.id.toString() : '',
      amount: preselectedInvoice
        ? parseFloat(preselectedInvoice.balance_due) > 0
          ? preselectedInvoice.balance_due.toString()
          : ''
        : '',
      payment_date: new Date().toISOString().split('T')[0],
      payment_method: 'Bank Transfer',
      reference: '',
      notes: '',
    });
    setShowRecordModal(true);
    loadInvoicesForDropdown();
  };

  // Change Invoice in Dropdown inside Modal
  const handleSelectInvoice = (invoiceIdStr) => {
    const invId = parseInt(invoiceIdStr, 10);
    const inv = allAvailableInvoices.find((i) => i.id === invId);
    setSelectedInvoice(inv || null);
    setNewPayment((prev) => ({
      ...prev,
      invoice_id: invoiceIdStr,
      amount: inv ? (parseFloat(inv.balance_due) > 0 ? inv.balance_due.toString() : '') : '',
    }));
    setFormError('');
  };

  // Submit Payment
  const handleRecordSubmit = async (e) => {
    e.preventDefault();
    setFormError('');

    const invoiceId = parseInt(newPayment.invoice_id, 10);
    if (!invoiceId) {
      setFormError('Please select an invoice to apply the payment.');
      return;
    }

    const amountNum = parseFloat(newPayment.amount);
    if (isNaN(amountNum) || amountNum <= 0) {
      setFormError('Payment amount must be a valid number greater than zero.');
      return;
    }

    if (selectedInvoice) {
      const balanceNum = parseFloat(selectedInvoice.balance_due);
      if (amountNum > balanceNum + 0.001) {
        setFormError(
          `Payment amount ($${amountNum.toFixed(2)}) exceeds remaining balance ($${balanceNum.toFixed(2)}).`
        );
        return;
      }
    }

    setIsSubmitting(true);
    try {
      await recordPayment({
        invoice_id: invoiceId,
        amount: amountNum,
        payment_date: newPayment.payment_date,
        payment_method: newPayment.payment_method,
        reference: newPayment.reference ? newPayment.reference.trim() : null,
        notes: newPayment.notes ? newPayment.notes.trim() : null,
      });

      setShowRecordModal(false);
      showNotification(`Payment of $${amountNum.toFixed(2)} recorded successfully.`);
      // Refresh both invoices (to update balances/statuses) and payments list
      fetchInvoicesList();
      fetchPaymentsList();
    } catch (err) {
      setFormError(err.message || 'Failed to record payment.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // View Payment History for an Invoice
  const handleOpenHistoryModal = async (invoice) => {
    setHistoryInvoice(invoice);
    setIsLoadingHistory(true);
    try {
      const res = await getInvoicePaymentSummary(invoice.id);
      setHistorySummary(res);
    } catch (err) {
      console.error('Failed to load payment history:', err);
      setHistorySummary(null);
    } finally {
      setIsLoadingHistory(false);
    }
  };

  // Submit Edit Payment
  const handleSaveEdit = async (e) => {
    e.preventDefault();
    if (!editingPayment) return;
    setEditError('');

    const amountNum = parseFloat(editingPayment.amount);
    if (isNaN(amountNum) || amountNum <= 0) {
      setEditError('Payment amount must be greater than zero.');
      return;
    }

    setIsUpdating(true);
    try {
      await updatePayment(editingPayment.id, {
        amount: amountNum,
        payment_date: editingPayment.payment_date,
        payment_method: editingPayment.payment_method,
        reference: editingPayment.reference ? editingPayment.reference.trim() : null,
        notes: editingPayment.notes ? editingPayment.notes.trim() : null,
      });

      setEditingPayment(null);
      showNotification('Payment record updated successfully.');
      fetchInvoicesList();
      fetchPaymentsList();
    } catch (err) {
      setEditError(err.message || 'Failed to update payment.');
    } finally {
      setIsUpdating(false);
    }
  };

  // Submit Delete Payment
  const handleConfirmDelete = async () => {
    if (!deletingPayment) return;
    setIsDeleting(true);
    try {
      await deletePayment(deletingPayment.id);
      showNotification('Payment record deleted successfully.');
      setDeletingPayment(null);
      fetchInvoicesList();
      fetchPaymentsList();
    } catch (err) {
      setErrorMessage(err.message || 'Failed to delete payment.');
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

  // Format Status Badge
  const renderPaymentStatusBadge = (status) => {
    const s = (status || 'UNPAID').toUpperCase();
    if (s === 'PAID') {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
          Paid
        </span>
      );
    }
    if (s === 'PARTIAL' || s === 'PARTIALLY_PAID' || s === 'PARTIALLY PAID') {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
          Partially Paid
        </span>
      );
    }
    if (s === 'OVERDUE') {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
          Overdue
        </span>
      );
    }
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
        Unpaid
      </span>
    );
  };

  // Format Review Status Badge
  const renderReviewStatusBadge = (inv) => {
    const isNeedsReview = inv.status === 'NEEDS_REVIEW';
    if (isNeedsReview) {
      return (
        <span
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-2xs font-medium bg-amber-50 text-amber-800 border border-amber-200"
          title="Review flag: Discrepancy detected during extraction. Payments are eligible with caution."
        >
          <AlertTriangle className="w-3 h-3 text-amber-600 shrink-0" />
          <span>Needs Review • Eligible</span>
        </span>
      );
    }
    return (
      <span
        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-2xs font-medium bg-teal-50 text-teal-800 border border-teal-200"
        title="Verified invoice: Validated and confirmed single source of truth."
      >
        <CheckCircle2 className="w-3 h-3 text-teal-600 shrink-0" />
        <span>Verified • Eligible</span>
      </span>
    );
  };

  // Due date countdown badge
  const renderDueDateBadge = (dueDateStr) => {
    if (!dueDateStr) return <span className="text-slate-400 text-xs">No due date</span>;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const due = new Date(dueDateStr);
    due.setHours(0, 0, 0, 0);
    const diffDays = Math.round((due - today) / (1000 * 60 * 60 * 24));

    if (diffDays < 0) {
      return (
        <div className="flex flex-col">
          <span className="font-medium text-slate-800">{dueDateStr}</span>
          <span className="text-2xs font-semibold text-rose-600">
            {Math.abs(diffDays)} day{Math.abs(diffDays) === 1 ? '' : 's'} overdue
          </span>
        </div>
      );
    }
    if (diffDays === 0) {
      return (
        <div className="flex flex-col">
          <span className="font-medium text-slate-800">{dueDateStr}</span>
          <span className="text-2xs font-semibold text-amber-600">Due today</span>
        </div>
      );
    }
    if (diffDays <= 7) {
      return (
        <div className="flex flex-col">
          <span className="font-medium text-slate-800">{dueDateStr}</span>
          <span className="text-2xs font-semibold text-teal-700">Due in {diffDays} days</span>
        </div>
      );
    }
    return (
      <div className="flex flex-col">
        <span className="font-medium text-slate-800">{dueDateStr}</span>
        <span className="text-2xs text-slate-500">In {diffDays} days</span>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Payment Tracker</h1>
          <p className="text-sm text-slate-500 mt-1">
            Single source of truth for invoice payment tracking, balance reconciliation, and payment history.
          </p>
        </div>

        <button
          onClick={() => handleOpenRecordModal()}
          className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-md text-sm font-medium transition-colors shadow-xs shrink-0"
        >
          <Plus className="w-4 h-4" />
          <span>Record Payment</span>
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

      {/* Top Financial KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-5 border border-slate-200 rounded-lg shadow-xs flex items-center gap-4">
          <div className="w-10 h-10 rounded-md bg-slate-100 text-slate-700 flex items-center justify-center shrink-0">
            <FileText className="w-5 h-5 text-slate-600" />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Total Invoiced
            </p>
            <p className="text-xl font-bold text-slate-900 mt-0.5">
              {formatCurrency(kpiTotalInvoiced)}
            </p>
            <p className="text-2xs text-slate-400 mt-0.5">{invoiceTotalCount} total invoices</p>
          </div>
        </div>

        <div className="bg-white p-5 border border-slate-200 rounded-lg shadow-xs flex items-center gap-4">
          <div className="w-10 h-10 rounded-md bg-emerald-50 text-emerald-700 flex items-center justify-center shrink-0">
            <DollarSign className="w-5 h-5" />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Total Paid Settled
            </p>
            <p className="text-xl font-bold text-emerald-700 mt-0.5">
              {formatCurrency(kpiTotalPaid)}
            </p>
            <p className="text-2xs text-slate-400 mt-0.5">{totalPaymentsCount} transactions recorded</p>
          </div>
        </div>

        <div className="bg-white p-5 border border-slate-200 rounded-lg shadow-xs flex items-center gap-4">
          <div className="w-10 h-10 rounded-md bg-amber-50 text-amber-700 flex items-center justify-center shrink-0">
            <CreditCard className="w-5 h-5" />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Outstanding Balance
            </p>
            <p className="text-xl font-bold text-amber-700 mt-0.5">
              {formatCurrency(kpiOutstanding)}
            </p>
            <p className="text-2xs text-slate-400 mt-0.5">Remaining to be settled</p>
          </div>
        </div>

        <div className="bg-white p-5 border border-slate-200 rounded-lg shadow-xs flex items-center gap-4">
          <div className="w-10 h-10 rounded-md bg-teal-50 text-teal-700 flex items-center justify-center shrink-0">
            <CheckCircle2 className="w-5 h-5" />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Settlement Status
            </p>
            <p className="text-xl font-bold text-slate-900 mt-0.5">
              {kpiPaidCount} / {invoiceTotalCount}
            </p>
            <p className="text-2xs text-slate-400 mt-0.5">Invoices fully paid</p>
          </div>
        </div>
      </div>

      {/* Tabs Switcher: Invoices Register vs Payment Transactions */}
      <div className="border-b border-slate-200 flex items-center justify-between">
        <div className="flex gap-2">
          <button
            onClick={() => setActiveTab('invoices')}
            className={`flex items-center gap-2 py-3 px-4 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'invoices'
                ? 'border-teal-600 text-teal-700 bg-teal-50/50'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <FileText className="w-4 h-4" />
            <span>Invoice Balances & Tracking</span>
            <span className="ml-1.5 px-2 py-0.5 text-2xs rounded-full bg-slate-100 text-slate-700 font-semibold">
              {invoiceTotalCount}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('transactions')}
            className={`flex items-center gap-2 py-3 px-4 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'transactions'
                ? 'border-teal-600 text-teal-700 bg-teal-50/50'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <CreditCard className="w-4 h-4" />
            <span>Payment Transaction Log</span>
            <span className="ml-1.5 px-2 py-0.5 text-2xs rounded-full bg-slate-100 text-slate-700 font-semibold">
              {totalPaymentsCount}
            </span>
          </button>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* TAB 1: Invoice Balances & Tracking Register (Single Source of Truth)       */}
      {/* ========================================================================= */}
      {activeTab === 'invoices' && (
        <div className="space-y-4">
          {/* Invoices Toolbar */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-white p-3 border border-slate-200 rounded-lg shadow-xs">
            <div className="relative flex-1 max-w-md">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                value={invoiceSearchQuery}
                onChange={(e) => setInvoiceSearchQuery(e.target.value)}
                placeholder="Search invoice #, supplier name..."
                className="w-full pl-9 pr-3 py-2 text-sm bg-slate-50 border border-slate-200 rounded-md text-slate-900 placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-teal-600 focus:bg-white transition-colors"
              />
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <Filter className="w-4 h-4 text-slate-400 hidden sm:inline" />
              <span className="text-xs font-medium text-slate-500 uppercase tracking-wider hidden sm:inline">
                Status:
              </span>
              <select
                value={invoiceStatusFilter}
                onChange={(e) => setInvoiceStatusFilter(e.target.value)}
                className="px-3 py-2 text-sm bg-white border border-slate-200 rounded-md text-slate-700 focus:outline-hidden focus:ring-2 focus:ring-teal-600 cursor-pointer"
              >
                <option value="ALL">All Payment Statuses</option>
                <option value="UNPAID">Unpaid</option>
                <option value="PARTIAL">Partially Paid</option>
                <option value="PAID">Paid</option>
                <option value="OVERDUE">Overdue</option>
              </select>
            </div>
          </div>

          {/* Invoices Table */}
          <div className="bg-white border border-slate-200 rounded-lg shadow-xs overflow-hidden">
            {isLoadingInvoices ? (
              <div className="py-16 text-center text-slate-500">
                <Loader2 className="w-8 h-8 animate-spin text-teal-600 mx-auto mb-3" />
                <p className="text-sm">Loading invoice balances...</p>
              </div>
            ) : invoices.length === 0 ? (
              <div className="py-16 px-4 text-center">
                <div className="w-12 h-12 bg-slate-100 text-slate-400 rounded-full flex items-center justify-center mx-auto mb-3">
                  <FileText className="w-6 h-6" />
                </div>
                <h3 className="text-base font-semibold text-slate-900">No invoices found</h3>
                <p className="text-sm text-slate-500 max-w-sm mx-auto mt-1 mb-5">
                  {invoiceSearchQuery || invoiceStatusFilter !== 'ALL'
                    ? 'No invoices match your selected search or status filters.'
                    : 'Invoices uploaded and saved in InvoiceIQ automatically appear here for real-time payment tracking.'}
                </p>
                {invoiceSearchQuery || invoiceStatusFilter !== 'ALL' ? (
                  <button
                    onClick={() => {
                      setInvoiceSearchQuery('');
                      setInvoiceStatusFilter('ALL');
                    }}
                    className="px-3.5 py-2 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-md"
                  >
                    Reset Filters
                  </button>
                ) : null}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm text-slate-700 divide-y divide-slate-200">
                  <thead className="bg-slate-50 text-xs font-semibold text-slate-600 uppercase tracking-wider">
                    <tr>
                      <th className="px-6 py-3.5">Invoice #</th>
                      <th className="px-6 py-3.5">Supplier / Vendor</th>
                      <th className="px-6 py-3.5">Due Date & Urgency</th>
                      <th className="px-6 py-3.5">Review & Eligibility</th>
                      <th className="px-6 py-3.5 text-right">Invoice Total</th>
                      <th className="px-6 py-3.5 text-right">Amount Paid</th>
                      <th className="px-6 py-3.5 text-right">Remaining Balance</th>
                      <th className="px-6 py-3.5 text-center">Payment Status</th>
                      <th className="px-6 py-3.5 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 bg-white">
                    {invoices.map((inv) => {
                      const balanceNum = parseFloat(inv.balance_due) || 0;
                      const hasBalance = balanceNum > 0.001;
                      return (
                        <tr key={inv.id} className="hover:bg-slate-50/70 transition-colors">
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="font-semibold text-slate-900">
                              {inv.invoice_number}
                            </div>
                            <div className="text-2xs text-slate-400 mt-0.5">
                              Dated: {inv.invoice_date || '—'}
                            </div>
                          </td>

                          <td className="px-6 py-4 text-slate-800 font-medium whitespace-nowrap">
                            {inv.vendor_name || '—'}
                          </td>

                          <td className="px-6 py-4 whitespace-nowrap">
                            {renderDueDateBadge(inv.due_date)}
                          </td>

                          <td className="px-6 py-4 whitespace-nowrap">
                            {renderReviewStatusBadge(inv)}
                          </td>

                          <td className="px-6 py-4 text-right font-medium text-slate-900 whitespace-nowrap">
                            {formatCurrency(inv.total_amount, inv.currency)}
                          </td>

                          <td className="px-6 py-4 text-right font-medium text-emerald-700 whitespace-nowrap">
                            {formatCurrency(inv.amount_paid, inv.currency)}
                          </td>

                          <td className="px-6 py-4 text-right font-bold whitespace-nowrap">
                            <span className={hasBalance ? 'text-amber-700' : 'text-slate-400'}>
                              {formatCurrency(inv.balance_due, inv.currency)}
                            </span>
                          </td>

                          <td className="px-6 py-4 text-center whitespace-nowrap">
                            {renderPaymentStatusBadge(inv.payment_status)}
                          </td>

                          <td className="px-6 py-4 text-right whitespace-nowrap">
                            <div className="flex items-center justify-end gap-2">
                              {hasBalance ? (
                                <button
                                  onClick={() => handleOpenRecordModal(inv)}
                                  className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-teal-600 hover:bg-teal-700 text-white rounded-md text-xs font-medium transition-colors shadow-2xs"
                                >
                                  <DollarSign className="w-3.5 h-3.5" />
                                  <span>Record Payment</span>
                                </button>
                              ) : (
                                <span className="inline-flex items-center gap-1 px-2.5 py-1 text-2xs font-semibold text-emerald-700 bg-emerald-50 rounded-md">
                                  <CheckCircle2 className="w-3 h-3" />
                                  Settled
                                </span>
                              )}

                              <button
                                onClick={() => handleOpenHistoryModal(inv)}
                                title="View Payment History"
                                className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-md transition-colors"
                              >
                                <History className="w-4 h-4" />
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
              <span>Showing {invoices.length} of {invoiceTotalCount} saved invoice records</span>
              <span className="font-medium text-teal-800">Single Source of Truth Active</span>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 2: Payment Transaction Log                                            */}
      {/* ========================================================================= */}
      {activeTab === 'transactions' && (
        <div className="space-y-4">
          {/* Search & Sort Toolbar */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-white p-3 border border-slate-200 rounded-lg shadow-xs">
            <div className="relative flex-1 max-w-md">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                value={paymentSearchQuery}
                onChange={(e) => setPaymentSearchQuery(e.target.value)}
                placeholder="Search by reference, invoice #, supplier, method..."
                className="w-full pl-9 pr-3 py-2 text-sm bg-slate-50 border border-slate-200 rounded-md text-slate-900 placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-teal-600 focus:bg-white transition-colors"
              />
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <span className="text-xs font-medium text-slate-500 uppercase tracking-wider hidden sm:inline">
                Sort by:
              </span>
              <select
                value={`${sortBy}_${sortOrder}`}
                onChange={(e) => {
                  const [col, ord] = e.target.value.split('_');
                  setSortBy(col);
                  setSortOrder(ord);
                }}
                className="px-3 py-2 text-sm bg-white border border-slate-200 rounded-md text-slate-700 focus:outline-hidden focus:ring-2 focus:ring-teal-600 cursor-pointer"
              >
                <option value="payment_date_desc">Payment Date: Newest first</option>
                <option value="payment_date_asc">Payment Date: Oldest first</option>
                <option value="amount_desc">Amount: Highest first</option>
                <option value="amount_asc">Amount: Lowest first</option>
              </select>
            </div>
          </div>

          {/* Payments Table */}
          <div className="bg-white border border-slate-200 rounded-lg shadow-xs overflow-hidden">
            {isLoadingPayments ? (
              <div className="py-16 text-center text-slate-500">
                <Loader2 className="w-8 h-8 animate-spin text-teal-600 mx-auto mb-3" />
                <p className="text-sm">Loading payment transactions...</p>
              </div>
            ) : payments.length === 0 ? (
              <div className="py-16 px-4 text-center">
                <div className="w-12 h-12 bg-slate-100 text-slate-400 rounded-full flex items-center justify-center mx-auto mb-3">
                  <CreditCard className="w-6 h-6" />
                </div>
                <h3 className="text-base font-semibold text-slate-900">No payment transactions recorded</h3>
                <p className="text-sm text-slate-500 max-w-sm mx-auto mt-1 mb-5">
                  {paymentSearchQuery
                    ? 'No payment records match your search query.'
                    : 'Record your first invoice payment from the Invoice Balances tab to update balances and track transaction history.'}
                </p>
                {paymentSearchQuery ? (
                  <button
                    onClick={() => setPaymentSearchQuery('')}
                    className="px-3.5 py-2 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-md"
                  >
                    Clear Search
                  </button>
                ) : (
                  <button
                    onClick={() => handleOpenRecordModal()}
                    className="inline-flex items-center gap-2 px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-md text-sm font-medium transition-colors shadow-xs"
                  >
                    <Plus className="w-4 h-4" />
                    <span>Record Payment</span>
                  </button>
                )}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm text-slate-700 divide-y divide-slate-200">
                  <thead className="bg-slate-50 text-xs font-semibold text-slate-600 uppercase tracking-wider">
                    <tr>
                      <th className="px-6 py-3.5">Payment Date</th>
                      <th className="px-6 py-3.5">Invoice #</th>
                      <th className="px-6 py-3.5">Supplier / Vendor</th>
                      <th className="px-6 py-3.5">Payment Method</th>
                      <th className="px-6 py-3.5">Reference ID</th>
                      <th className="px-6 py-3.5 text-right">Amount Paid</th>
                      <th className="px-6 py-3.5 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 bg-white">
                    {payments.map((p) => (
                      <tr key={p.id} className="hover:bg-slate-50/70 transition-colors">
                        <td className="px-6 py-4 font-medium text-slate-900 whitespace-nowrap">
                          {p.payment_date}
                        </td>

                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className="font-semibold text-slate-800">
                            {p.invoice_number || `Invoice #${p.invoice_id}`}
                          </span>
                        </td>

                        <td className="px-6 py-4 text-slate-700 whitespace-nowrap">
                          {p.vendor_name || '—'}
                        </td>

                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200">
                            {p.payment_method}
                          </span>
                        </td>

                        <td className="px-6 py-4 text-slate-600 whitespace-nowrap text-xs font-mono">
                          {p.reference || '—'}
                        </td>

                        <td className="px-6 py-4 text-right font-semibold text-slate-900 whitespace-nowrap">
                          {formatCurrency(p.amount, p.currency)}
                        </td>

                        <td className="px-6 py-4 text-right whitespace-nowrap">
                          <div className="flex items-center justify-end gap-1.5">
                            <button
                              onClick={() => {
                                setEditingPayment({
                                  id: p.id,
                                  amount: p.amount.toString(),
                                  payment_date: p.payment_date,
                                  payment_method: p.payment_method,
                                  reference: p.reference || '',
                                  notes: p.notes || '',
                                  invoice_number: p.invoice_number,
                                });
                                setEditError('');
                              }}
                              title="Edit Payment"
                              className="p-1.5 text-slate-400 hover:text-teal-700 hover:bg-teal-50 rounded-md transition-colors"
                            >
                              <Edit2 className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => setDeletingPayment(p)}
                              title="Delete Payment"
                              className="p-1.5 text-slate-400 hover:text-red-700 hover:bg-red-50 rounded-md transition-colors"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Footer */}
            <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex items-center justify-between text-xs text-slate-500">
              <span>Showing {payments.length} of {totalPaymentsCount} transactions</span>
              <span className="text-slate-500 font-medium">Recorded Total: {formatCurrency(totalRecordedAmount)}</span>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODAL 1: Record Payment Modal                                             */}
      {/* ========================================================================= */}
      {showRecordModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
          <div className="bg-white rounded-lg border border-slate-200 shadow-xl max-w-lg w-full overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded bg-teal-600 flex items-center justify-center text-white">
                  <Plus className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-base font-semibold text-slate-900">Record Payment</h3>
                  <p className="text-xs text-slate-500">Apply a full or partial payment to a saved invoice</p>
                </div>
              </div>
              <button
                onClick={() => setShowRecordModal(false)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-md"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleRecordSubmit} className="p-6 space-y-4">
              {formError && (
                <div className="flex items-start gap-2.5 p-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-md">
                  <AlertCircle className="w-4 h-4 shrink-0 text-red-600 mt-0.5" />
                  <div className="flex-1">{formError}</div>
                </div>
              )}

              {/* Review status caution banner if invoice needs review */}
              {selectedInvoice && selectedInvoice.status === 'NEEDS_REVIEW' && (
                <div className="p-3 bg-amber-50 border border-amber-200 rounded-md text-xs flex items-start gap-2.5 text-amber-900">
                  <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold block">Notice: Needs Review</span>
                    <span>
                      This invoice was flagged during extraction for arithmetic or date review. Payment is permitted, but please verify the amounts against your supplier records.
                    </span>
                  </div>
                </div>
              )}

              {/* Select Target Invoice */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                  Target Invoice *
                </label>
                <select
                  required
                  value={newPayment.invoice_id}
                  onChange={(e) => handleSelectInvoice(e.target.value)}
                  className="w-full px-3 py-2 text-sm bg-white border border-slate-300 rounded-md text-slate-900 focus:ring-2 focus:ring-teal-600 focus:outline-hidden"
                >
                  <option value="">-- Choose a saved invoice to pay --</option>
                  {allAvailableInvoices.map((inv) => (
                    <option key={inv.id} value={inv.id}>
                      {inv.invoice_number} ({inv.vendor_name}) — Total: ${inv.total_amount} | Balance: ${inv.balance_due} {inv.status === 'NEEDS_REVIEW' ? '⚠' : ''}
                    </option>
                  ))}
                </select>
              </div>

              {/* Remaining Balance Callout */}
              {selectedInvoice && (
                <div className="p-3 bg-teal-50 border border-teal-200 rounded-md text-xs flex justify-between items-center text-teal-900">
                  <div>
                    <span className="font-semibold">{selectedInvoice.vendor_name}</span>
                    <span className="text-teal-700 block text-2xs">
                      Due: {selectedInvoice.due_date || 'No due date'}
                    </span>
                  </div>
                  <div className="text-right">
                    <span className="text-slate-500 block text-2xs">Remaining Balance</span>
                    <span className="font-bold text-sm text-teal-800">
                      ${parseFloat(selectedInvoice.balance_due).toFixed(2)} {selectedInvoice.currency}
                    </span>
                  </div>
                </div>
              )}

              {/* Payment Amount */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                  Payment Amount *
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 font-medium">
                    $
                  </span>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    max={selectedInvoice ? parseFloat(selectedInvoice.balance_due) : undefined}
                    required
                    value={newPayment.amount}
                    onChange={(e) => setNewPayment({ ...newPayment, amount: e.target.value })}
                    placeholder="0.00"
                    className="w-full pl-8 pr-3 py-2 text-sm font-semibold border border-slate-300 rounded-md text-slate-900 focus:ring-2 focus:ring-teal-600 focus:outline-hidden"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                {/* Payment Date */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                    Payment Date *
                  </label>
                  <input
                    type="date"
                    required
                    value={newPayment.payment_date}
                    onChange={(e) =>
                      setNewPayment({ ...newPayment, payment_date: e.target.value })
                    }
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-md text-slate-900 focus:ring-2 focus:ring-teal-600 focus:outline-hidden"
                  />
                </div>

                {/* Payment Method */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                    Method *
                  </label>
                  <select
                    value={newPayment.payment_method}
                    onChange={(e) =>
                      setNewPayment({ ...newPayment, payment_method: e.target.value })
                    }
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-md text-slate-900 focus:ring-2 focus:ring-teal-600 focus:outline-hidden"
                  >
                    <option value="Bank Transfer">Bank Transfer</option>
                    <option value="Credit Card">Credit Card</option>
                    <option value="ACH">ACH Transfer</option>
                    <option value="Check">Check</option>
                    <option value="Cash">Cash</option>
                    <option value="Wire Transfer">Wire Transfer</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
              </div>

              {/* Reference ID */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                  Reference / Transaction ID <span className="text-slate-400 font-normal lowercase">(optional)</span>
                </label>
                <input
                  type="text"
                  value={newPayment.reference}
                  onChange={(e) => setNewPayment({ ...newPayment, reference: e.target.value })}
                  placeholder="e.g. TXN-998822 or Check #402"
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-md text-slate-900 focus:ring-2 focus:ring-teal-600 focus:outline-hidden"
                />
              </div>

              {/* Notes */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                  Notes <span className="text-slate-400 font-normal lowercase">(optional)</span>
                </label>
                <textarea
                  rows={2}
                  value={newPayment.notes}
                  onChange={(e) => setNewPayment({ ...newPayment, notes: e.target.value })}
                  placeholder="Internal audit notes or payment memo..."
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-md text-slate-900 focus:ring-2 focus:ring-teal-600 focus:outline-hidden"
                />
              </div>

              {/* Modal Buttons */}
              <div className="pt-2 flex justify-end gap-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowRecordModal(false)}
                  disabled={isSubmitting}
                  className="px-3.5 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100 rounded-md"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="inline-flex items-center gap-1.5 px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-md text-xs font-medium transition-colors disabled:opacity-70 shadow-xs"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Recording...</span>
                    </>
                  ) : (
                    <span>Record Payment</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODAL 2: Invoice Payment History Modal                                    */}
      {/* ========================================================================= */}
      {historyInvoice && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
          <div className="bg-white rounded-lg border border-slate-200 shadow-xl max-w-lg w-full overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div className="flex items-center gap-2">
                <History className="w-5 h-5 text-teal-600" />
                <div>
                  <h3 className="text-base font-semibold text-slate-900">
                    Payment History: {historyInvoice.invoice_number}
                  </h3>
                  <p className="text-xs text-slate-500">{historyInvoice.vendor_name}</p>
                </div>
              </div>
              <button
                onClick={() => setHistoryInvoice(null)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-md"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              {/* Balances summary */}
              <div className="grid grid-cols-3 gap-3 p-3 bg-slate-50 border border-slate-200 rounded-md text-center">
                <div>
                  <span className="text-2xs text-slate-500 uppercase font-semibold">Total Amount</span>
                  <p className="text-sm font-bold text-slate-900">
                    {formatCurrency(historyInvoice.total_amount, historyInvoice.currency)}
                  </p>
                </div>
                <div>
                  <span className="text-2xs text-slate-500 uppercase font-semibold">Amount Paid</span>
                  <p className="text-sm font-bold text-emerald-700">
                    {formatCurrency(historyInvoice.amount_paid, historyInvoice.currency)}
                  </p>
                </div>
                <div>
                  <span className="text-2xs text-slate-500 uppercase font-semibold">Balance Due</span>
                  <p className="text-sm font-bold text-amber-700">
                    {formatCurrency(historyInvoice.balance_due, historyInvoice.currency)}
                  </p>
                </div>
              </div>

              {/* Transactions List */}
              {isLoadingHistory ? (
                <div className="py-8 text-center text-slate-500">
                  <Loader2 className="w-6 h-6 animate-spin text-teal-600 mx-auto mb-2" />
                  <p className="text-xs">Fetching payment history...</p>
                </div>
              ) : !historySummary || !historySummary.payments || historySummary.payments.length === 0 ? (
                <div className="py-8 text-center">
                  <CreditCard className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                  <p className="text-sm font-medium text-slate-700">No payments recorded yet</p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    This invoice is currently unpaid.
                  </p>
                </div>
              ) : (
                <div className="space-y-2 max-h-64 overflow-y-auto divide-y divide-slate-100">
                  {historySummary.payments.map((p) => (
                    <div key={p.id} className="pt-2 flex items-center justify-between text-xs">
                      <div>
                        <div className="font-semibold text-slate-800">
                          {p.payment_date} • {p.payment_method}
                        </div>
                        <div className="text-slate-500 text-2xs">
                          {p.reference ? `Ref: ${p.reference}` : 'No reference'}
                          {p.notes ? ` • Note: ${p.notes}` : ''}
                        </div>
                      </div>
                      <div className="font-bold text-sm text-emerald-700">
                        +{formatCurrency(p.amount, historyInvoice.currency)}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Modal footer */}
              <div className="pt-3 flex justify-between items-center border-t border-slate-100">
                {parseFloat(historyInvoice.balance_due) > 0.001 ? (
                  <button
                    onClick={() => {
                      const inv = historyInvoice;
                      setHistoryInvoice(null);
                      handleOpenRecordModal(inv);
                    }}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-teal-600 hover:bg-teal-700 text-white rounded-md text-xs font-medium"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Record Payment</span>
                  </button>
                ) : (
                  <span className="text-xs font-semibold text-emerald-700 flex items-center gap-1">
                    <CheckCircle2 className="w-4 h-4" /> Fully Settled
                  </span>
                )}

                <button
                  type="button"
                  onClick={() => setHistoryInvoice(null)}
                  className="px-3.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100 rounded-md"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODAL 3: Edit Payment Modal                                               */}
      {/* ========================================================================= */}
      {editingPayment && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
          <div className="bg-white rounded-lg border border-slate-200 shadow-xl max-w-md w-full overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <h3 className="text-base font-semibold text-slate-900">
                Edit Payment ({editingPayment.invoice_number})
              </h3>
              <button
                onClick={() => setEditingPayment(null)}
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

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                  Payment Amount *
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  required
                  value={editingPayment.amount}
                  onChange={(e) =>
                    setEditingPayment({ ...editingPayment, amount: e.target.value })
                  }
                  className="w-full px-3 py-2 text-sm font-semibold border border-slate-300 rounded-md"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                    Date *
                  </label>
                  <input
                    type="date"
                    required
                    value={editingPayment.payment_date}
                    onChange={(e) =>
                      setEditingPayment({ ...editingPayment, payment_date: e.target.value })
                    }
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-md"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                    Method *
                  </label>
                  <select
                    value={editingPayment.payment_method}
                    onChange={(e) =>
                      setEditingPayment({ ...editingPayment, payment_method: e.target.value })
                    }
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-md"
                  >
                    <option value="Bank Transfer">Bank Transfer</option>
                    <option value="Credit Card">Credit Card</option>
                    <option value="ACH">ACH Transfer</option>
                    <option value="Check">Check</option>
                    <option value="Cash">Cash</option>
                    <option value="Wire Transfer">Wire Transfer</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                  Reference ID
                </label>
                <input
                  type="text"
                  value={editingPayment.reference}
                  onChange={(e) =>
                    setEditingPayment({ ...editingPayment, reference: e.target.value })
                  }
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-md"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                  Notes
                </label>
                <textarea
                  rows={2}
                  value={editingPayment.notes}
                  onChange={(e) =>
                    setEditingPayment({ ...editingPayment, notes: e.target.value })
                  }
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-md"
                />
              </div>

              <div className="pt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setEditingPayment(null)}
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
      {/* MODAL 4: Delete Confirmation Dialog                                       */}
      {/* ========================================================================= */}
      {deletingPayment && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
          <div className="bg-white rounded-lg border border-slate-200 shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-full bg-red-100 text-red-600 flex items-center justify-center shrink-0">
                <Trash2 className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-slate-900">Delete Payment Record</h3>
                <p className="text-xs text-slate-500 mt-1">
                  Are you sure you want to delete payment of{' '}
                  <span className="font-semibold text-slate-800">
                    {formatCurrency(deletingPayment.amount, deletingPayment.currency)}
                  </span>{' '}
                  for{' '}
                  <span className="font-semibold text-slate-800">
                    {deletingPayment.invoice_number || `Invoice #${deletingPayment.invoice_id}`}
                  </span>
                  ? The invoice balance will automatically increase.
                </p>
              </div>
            </div>

            <div className="pt-2 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setDeletingPayment(null)}
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
                {isDeleting ? 'Deleting...' : 'Delete Payment'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
