import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  BrainCircuit,
  AlertCircle,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Search,
  Loader2,
  ShieldCheck,
  FileText,
  Building,
  Info,
  ArrowRight,
  Sparkles,
  Check,
  RotateCcw,
  X,
  ShieldAlert,
} from 'lucide-react';
import {
  getAnomalies,
  runAssessment,
  markAnomalyReviewed,
  unmarkAnomalyReviewed,
} from '../api/anomalies';

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

export default function AnomalyDetection() {
  const navigate = useNavigate();
  const [data, setData] = useState({
    status: 'NOT_ASSESSED',
    message: '',
    total_invoices: 0,
    assessed_count: 0,
    anomalous_count: 0,
    normal_count: 0,
    reviewed_count: 0,
    unreviewed_anomalous_count: 0,
    min_required: 5,
    disclaimer: '',
    items: [],
  });

  const [isLoading, setIsLoading] = useState(true);
  const [isAssessing, setIsAssessing] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  // Filtering & Search
  const [activeTab, setActiveTab] = useState('ALL'); // 'ALL' | 'UNREVIEWED' | 'POTENTIALLY_UNUSUAL' | 'REVIEWED' | 'NO_UNUSUAL_PATTERN'
  const [searchQuery, setSearchQuery] = useState('');

  // Review Modal State
  const [reviewingItem, setReviewingItem] = useState(null);
  const [reviewNotes, setReviewNotes] = useState('');
  const [isSubmittingReview, setIsSubmittingReview] = useState(false);

  const fetchAssessments = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage('');
    try {
      const res = await getAnomalies();
      setData(res);
    } catch (err) {
      setErrorMessage(err.message || 'Failed to load anomaly detection results.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAssessments();
  }, [fetchAssessments]);

  const handleRunAssessment = async () => {
    setIsAssessing(true);
    setErrorMessage('');
    setSuccessMessage('');
    try {
      const res = await runAssessment();
      setData(res);
      if (res.status === 'COMPLETED') {
        setSuccessMessage(
          `Assessment completed successfully. Evaluated ${res.assessed_count} invoices with Isolation Forest.`
        );
      } else if (res.status === 'INSUFFICIENT_DATA') {
        setErrorMessage(res.message);
      }
    } catch (err) {
      setErrorMessage(err.message || 'Error occurred while running anomaly assessment.');
    } finally {
      setIsAssessing(false);
    }
  };

  const handleOpenReview = (item) => {
    setReviewingItem(item);
    setReviewNotes(item.review_notes || '');
  };

  const handleConfirmReview = async () => {
    if (!reviewingItem) return;
    setIsSubmittingReview(true);
    setErrorMessage('');
    try {
      await markAnomalyReviewed(reviewingItem.id || reviewingItem.invoice_id, reviewNotes);
      setSuccessMessage(`Invoice #${reviewingItem.invoice_number} marked as reviewed.`);
      setReviewingItem(null);
      await fetchAssessments();
    } catch (err) {
      setErrorMessage(err.message || 'Failed to submit review.');
    } finally {
      setIsSubmittingReview(false);
    }
  };

  const handleResetReview = async () => {
    if (!reviewingItem) return;
    setIsSubmittingReview(true);
    setErrorMessage('');
    try {
      await unmarkAnomalyReviewed(reviewingItem.id || reviewingItem.invoice_id);
      setSuccessMessage(`Reset review status for invoice #${reviewingItem.invoice_number}.`);
      setReviewingItem(null);
      await fetchAssessments();
    } catch (err) {
      setErrorMessage(err.message || 'Failed to reset review status.');
    } finally {
      setIsSubmittingReview(false);
    }
  };

  // Filtered Items
  const displayedItems = (data.items || []).filter((item) => {
    // Tab filter
    if (activeTab === 'POTENTIALLY_UNUSUAL' && !item.is_anomaly) return false;
    if (activeTab === 'NO_UNUSUAL_PATTERN' && item.is_anomaly) return false;
    if (activeTab === 'UNREVIEWED' && (!item.is_anomaly || item.is_reviewed)) return false;
    if (activeTab === 'REVIEWED' && !item.is_reviewed) return false;

    // Search query filter
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      const matchInv = item.invoice_number?.toLowerCase().includes(q);
      const matchVendor = item.vendor_name?.toLowerCase().includes(q);
      return matchInv || matchVendor;
    }
    return true;
  });

  const renderRiskBadge = (riskLevel, isAnomaly) => {
    if (!isAnomaly) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-teal-50 text-teal-800 border border-teal-200">
          <ShieldCheck className="w-3 h-3 text-teal-600 shrink-0" />
          <span>Low Risk</span>
        </span>
      );
    }
    if (riskLevel === 'HIGH') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-300">
          <ShieldAlert className="w-3 h-3 text-rose-600 shrink-0" />
          <span>High Variation</span>
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-800 border border-amber-300">
        <AlertTriangle className="w-3 h-3 text-amber-600 shrink-0" />
        <span>Moderate</span>
      </span>
    );
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
              Anomaly Detection
            </h1>
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-teal-50 text-teal-700 border border-teal-200">
              <Sparkles className="w-3 h-3 text-teal-600" />
              Machine Learning
            </span>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            Statistical outlier screening powered by Isolation Forest (scikit-learn).
          </p>
        </div>

        <button
          onClick={handleRunAssessment}
          disabled={isAssessing || isLoading}
          className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-teal-600 hover:bg-teal-700 disabled:opacity-50 text-white rounded-md text-sm font-medium transition-colors shadow-xs shrink-0"
        >
          {isAssessing ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Fitting Model...</span>
            </>
          ) : (
            <>
              <RefreshCw className="w-4 h-4" />
              <span>{data.assessed_count > 0 ? 'Refresh Assessment' : 'Run Assessment'}</span>
            </>
          )}
        </button>
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

      {/* Prominent Screening Signal Notice */}
      <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 flex items-start gap-3 text-xs text-slate-600 shadow-xs">
        <Info className="w-5 h-5 text-teal-700 shrink-0 mt-0.5" />
        <div className="leading-relaxed">
          <span className="font-semibold text-slate-800">Automated Screening Signal: </span>
          This tool uses an unsupervised Isolation Forest model to detect statistical deviations
          in invoice amounts, vendor expense baselines, and financial ratios.
          <span className="font-medium text-slate-700"> A flag indicates an unusual pattern for review, NOT proof of fraud or accounting error.</span>{' '}
          Auditor reviews confirm verification and never alter invoice balances or payment statuses.
        </div>
      </div>

      {/* State 1: Insufficient Data State */}
      {data.status === 'INSUFFICIENT_DATA' ? (
        <div className="bg-white border border-slate-200 rounded-lg p-8 shadow-xs text-center">
          <div className="max-w-md mx-auto space-y-4">
            <div className="w-12 h-12 bg-amber-50 text-amber-600 rounded-full flex items-center justify-center mx-auto">
              <BrainCircuit className="w-6 h-6" />
            </div>
            <h2 className="text-lg font-semibold text-slate-900">
              More Invoices Required for ML Training
            </h2>
            <p className="text-xs text-slate-600 leading-relaxed">
              The Isolation Forest algorithm requires at least{' '}
              <span className="font-semibold text-slate-800">{data.min_required} saved invoices</span>{' '}
              to establish baseline statistical distributions. Training on fewer invoices would
              produce arbitrary splits and false positives.
            </p>

            {/* Progress indicator */}
            <div className="p-3 bg-slate-50 border border-slate-200 rounded-md text-xs">
              <div className="flex justify-between font-medium text-slate-700 mb-1.5">
                <span>Current Invoices: {data.total_invoices}</span>
                <span>Required: {data.min_required}</span>
              </div>
              <div className="w-full bg-slate-200 rounded-full h-2 overflow-hidden">
                <div
                  className="bg-teal-600 h-2 rounded-full transition-all duration-500"
                  style={{
                    width: `${Math.min(100, (data.total_invoices / data.min_required) * 100)}%`,
                  }}
                />
              </div>
            </div>

            <button
              onClick={() => navigate('/invoices')}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-md text-xs font-medium transition-colors shadow-xs"
            >
              <span>Upload More Invoices</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      ) : data.status === 'NOT_ASSESSED' && data.assessed_count === 0 ? (
        /* State 2: Ready to Assess */
        <div className="bg-white border border-slate-200 rounded-lg p-8 shadow-xs text-center">
          <div className="max-w-md mx-auto space-y-3">
            <div className="w-12 h-12 bg-teal-50 text-teal-600 rounded-full flex items-center justify-center mx-auto">
              <BrainCircuit className="w-6 h-6" />
            </div>
            <h2 className="text-base font-semibold text-slate-900">Ready for Analysis</h2>
            <p className="text-xs text-slate-600 leading-relaxed">
              You have {data.total_invoices} saved invoices available. Click below to run the
              Isolation Forest screening algorithm to identify unusual spending patterns.
            </p>
            <button
              onClick={handleRunAssessment}
              disabled={isAssessing}
              className="inline-flex items-center gap-2 px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-md text-xs font-medium transition-colors shadow-xs"
            >
              {isAssessing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
              <span>Run Initial Assessment</span>
            </button>
          </div>
        </div>
      ) : (
        /* State 3: Active Assessment Results */
        <div className="space-y-6">
          {/* KPI Summary Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Total Assessed */}
            <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-xs">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                Invoices Assessed
              </span>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-2xl font-bold text-slate-900">
                  {data.assessed_count}
                </span>
                <span className="text-xs text-slate-500">total records</span>
              </div>
              <p className="mt-1 text-xs text-slate-400">100% user-isolated evaluation</p>
            </div>

            {/* Potentially Unusual */}
            <div className="bg-white border border-rose-200 rounded-lg p-5 shadow-xs">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-rose-700 uppercase tracking-wider">
                  Potentially Unusual
                </span>
                <div className="w-7 h-7 rounded-full bg-rose-50 text-rose-600 flex items-center justify-center">
                  <AlertTriangle className="w-3.5 h-3.5" />
                </div>
              </div>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-2xl font-bold text-slate-900">
                  {data.anomalous_count}
                </span>
                <span className="text-xs text-rose-600 font-medium">flagged</span>
              </div>
              <p className="mt-1 text-xs text-slate-500">
                {data.unreviewed_anomalous_count} pending auditor review
              </p>
            </div>

            {/* Confirmed Reviewed */}
            <div className="bg-white border border-sky-200 rounded-lg p-5 shadow-xs">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-sky-800 uppercase tracking-wider">
                  Reviewed Flags
                </span>
                <div className="w-7 h-7 rounded-full bg-sky-50 text-sky-600 flex items-center justify-center">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                </div>
              </div>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-2xl font-bold text-slate-900">
                  {data.reviewed_count}
                </span>
                <span className="text-xs text-sky-700 font-medium">verified</span>
              </div>
              <p className="mt-1 text-xs text-slate-500">Audit trail confirmed</p>
            </div>

            {/* Normal Patterns */}
            <div className="bg-white border border-teal-200 rounded-lg p-5 shadow-xs">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-teal-800 uppercase tracking-wider">
                  Normal Pattern
                </span>
                <div className="w-7 h-7 rounded-full bg-teal-50 text-teal-600 flex items-center justify-center">
                  <ShieldCheck className="w-3.5 h-3.5" />
                </div>
              </div>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-2xl font-bold text-slate-900">
                  {data.normal_count}
                </span>
                <span className="text-xs text-teal-700 font-medium">within bounds</span>
              </div>
              <p className="mt-1 text-xs text-slate-500">Conforming to expectations</p>
            </div>
          </div>

          {/* Table Card */}
          <div className="bg-white border border-slate-200 rounded-lg shadow-xs overflow-hidden">
            {/* Filter Tabs and Search Bar */}
            <div className="p-4 border-b border-slate-200 bg-slate-50/50 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
              {/* Status Filter Tabs */}
              <div className="flex items-center gap-1.5 flex-wrap">
                <button
                  onClick={() => setActiveTab('ALL')}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                    activeTab === 'ALL'
                      ? 'bg-slate-900 text-white shadow-xs'
                      : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  All ({data.assessed_count})
                </button>
                <button
                  onClick={() => setActiveTab('UNREVIEWED')}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                    activeTab === 'UNREVIEWED'
                      ? 'bg-amber-700 text-white shadow-xs'
                      : 'bg-white border border-slate-200 text-amber-800 hover:bg-amber-50'
                  }`}
                >
                  Needs Review ({data.unreviewed_anomalous_count})
                </button>
                <button
                  onClick={() => setActiveTab('POTENTIALLY_UNUSUAL')}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                    activeTab === 'POTENTIALLY_UNUSUAL'
                      ? 'bg-rose-700 text-white shadow-xs'
                      : 'bg-white border border-slate-200 text-rose-700 hover:bg-rose-50'
                  }`}
                >
                  All Flagged ({data.anomalous_count})
                </button>
                <button
                  onClick={() => setActiveTab('REVIEWED')}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                    activeTab === 'REVIEWED'
                      ? 'bg-sky-700 text-white shadow-xs'
                      : 'bg-white border border-slate-200 text-sky-800 hover:bg-sky-50'
                  }`}
                >
                  Reviewed ({data.reviewed_count})
                </button>
                <button
                  onClick={() => setActiveTab('NO_UNUSUAL_PATTERN')}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                    activeTab === 'NO_UNUSUAL_PATTERN'
                      ? 'bg-teal-700 text-white shadow-xs'
                      : 'bg-white border border-slate-200 text-teal-800 hover:bg-teal-50'
                  }`}
                >
                  Normal ({data.normal_count})
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

            {/* Assessment Table */}
            {isLoading ? (
              <div className="p-12 text-center text-slate-500">
                <Loader2 className="w-8 h-8 animate-spin mx-auto text-teal-600 mb-2" />
                <p className="text-sm">Loading assessment records...</p>
              </div>
            ) : displayedItems.length === 0 ? (
              <div className="p-12 text-center">
                <div className="w-12 h-12 bg-slate-100 text-slate-400 rounded-full flex items-center justify-center mx-auto mb-3">
                  <BrainCircuit className="w-6 h-6" />
                </div>
                <h3 className="text-sm font-semibold text-slate-900">No invoices match this view</h3>
                <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                  {searchQuery
                    ? 'Try clearing the search query to see more results.'
                    : 'There are no invoices in the selected status category.'}
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm text-slate-700 divide-y divide-slate-200">
                  <thead className="bg-slate-50 text-xs font-semibold text-slate-600 uppercase tracking-wider">
                    <tr>
                      <th className="px-5 py-3.5">Invoice #</th>
                      <th className="px-5 py-3.5">Supplier / Vendor</th>
                      <th className="px-5 py-3.5">Date</th>
                      <th className="px-5 py-3.5 text-right">Amount</th>
                      <th className="px-5 py-3.5 text-center">Risk Level</th>
                      <th className="px-5 py-3.5">Evidence & Statistical Explanation</th>
                      <th className="px-5 py-3.5 text-center">Audit Review</th>
                      <th className="px-5 py-3.5 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 bg-white">
                    {displayedItems.map((item) => (
                      <tr
                        key={item.invoice_id}
                        className={`transition-colors hover:bg-slate-50/70 ${
                          item.is_anomaly && !item.is_reviewed ? 'bg-rose-50/20' : ''
                        }`}
                      >
                        {/* Invoice Number */}
                        <td className="px-5 py-4 font-medium text-slate-900 whitespace-nowrap">
                          {item.invoice_number}
                        </td>

                        {/* Vendor Name */}
                        <td className="px-5 py-4 text-slate-800 whitespace-nowrap">
                          {item.vendor_name}
                        </td>

                        {/* Invoice Date */}
                        <td className="px-5 py-4 text-slate-600 whitespace-nowrap text-xs">
                          {item.invoice_date}
                        </td>

                        {/* Total Amount */}
                        <td className="px-5 py-4 text-right font-semibold text-slate-900 whitespace-nowrap">
                          {formatCurrency(item.total_amount, item.currency)}
                        </td>

                        {/* Risk Badge */}
                        <td className="px-5 py-4 text-center whitespace-nowrap">
                          {renderRiskBadge(item.risk_level, item.is_anomaly)}
                        </td>

                        {/* Explanation & Rule Warnings */}
                        <td className="px-5 py-4 text-xs text-slate-600 max-w-md leading-relaxed">
                          <p>{item.explanation}</p>
                          {item.rule_warnings && item.rule_warnings.length > 0 && (
                            <div className="mt-1.5 space-y-0.5">
                              {item.rule_warnings.map((rw, i) => (
                                <div
                                  key={i}
                                  className="text-[11px] font-medium text-rose-700 flex items-center gap-1"
                                >
                                  <span>&bull;</span>
                                  <span>{rw}</span>
                                </div>
                              ))}
                            </div>
                          )}
                          {item.is_reviewed && item.review_notes && (
                            <p className="mt-1 text-[11px] text-sky-800 bg-sky-50 p-1.5 rounded border border-sky-200">
                              <span className="font-semibold">Review note: </span>
                              {item.review_notes}
                            </p>
                          )}
                        </td>

                        {/* Review Status Badge */}
                        <td className="px-5 py-4 text-center whitespace-nowrap">
                          {item.is_reviewed ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                              <Check className="w-3 h-3 text-emerald-600" />
                              <span>Reviewed</span>
                            </span>
                          ) : item.is_anomaly ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-800 border border-amber-300">
                              <AlertCircle className="w-3 h-3 text-amber-600" />
                              <span>Needs Review</span>
                            </span>
                          ) : (
                            <span className="text-xs text-slate-400">&mdash;</span>
                          )}
                        </td>

                        {/* Actions */}
                        <td className="px-5 py-4 text-right whitespace-nowrap">
                          <div className="flex items-center justify-end gap-1.5">
                            {item.is_anomaly && (
                              <button
                                onClick={() => handleOpenReview(item)}
                                className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-teal-700 bg-teal-50 hover:bg-teal-100 border border-teal-200 rounded-md transition-colors"
                                title="Inspect and confirm audit review"
                              >
                                <span>{item.is_reviewed ? 'Edit Review' : 'Audit Review'}</span>
                              </button>
                            )}
                            <button
                              onClick={() => navigate('/invoices')}
                              className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-md transition-colors"
                              title="View Invoice in Management Page"
                            >
                              <span>View</span>
                              <ArrowRight className="w-3.5 h-3.5" />
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
            <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-500 gap-2">
              <span>
                Showing {displayedItems.length} of {data.assessed_count} assessed records
              </span>
              <span>Model: {data.items[0]?.model_version || 'IsolationForest-v1.2'} &bull; RobustScaler</span>
            </div>
          </div>
        </div>
      )}

      {/* Review Modal Dialog */}
      {reviewingItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-lg w-full overflow-hidden border border-slate-200">
            {/* Modal Header */}
            <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50/70">
              <div className="flex items-center gap-2">
                <BrainCircuit className="w-5 h-5 text-teal-600" />
                <h3 className="text-base font-semibold text-slate-900">
                  Audit Review: Inv #{reviewingItem.invoice_number}
                </h3>
              </div>
              <button
                onClick={() => setReviewingItem(null)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-5 space-y-4">
              <div className="p-3 bg-slate-50 rounded-md border border-slate-200 text-xs space-y-1.5">
                <div className="flex justify-between">
                  <span className="text-slate-500 font-medium">Supplier / Vendor:</span>
                  <span className="text-slate-800 font-semibold">{reviewingItem.vendor_name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500 font-medium">Total Amount:</span>
                  <span className="text-slate-800 font-bold">
                    {formatCurrency(reviewingItem.total_amount, reviewingItem.currency)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500 font-medium">Risk Classification:</span>
                  <span>{renderRiskBadge(reviewingItem.risk_level, reviewingItem.is_anomaly)}</span>
                </div>
              </div>

              {/* Observed factors */}
              <div className="text-xs space-y-1">
                <span className="font-semibold text-slate-700">Observed Screening Evidence:</span>
                <p className="text-slate-600 bg-amber-50/60 p-2.5 rounded border border-amber-200/80 leading-relaxed">
                  {reviewingItem.explanation}
                </p>
              </div>

              {/* Integrity Disclaimer */}
              <div className="p-3 bg-teal-50/60 rounded border border-teal-200 text-[11px] text-teal-900 flex items-start gap-2">
                <Info className="w-4 h-4 text-teal-700 shrink-0 mt-0.5" />
                <span>
                  Confirming review records a permanent verification audit note. It will{' '}
                  <span className="font-semibold">never alter the invoice amount, tax figures, or payment status.</span>
                </span>
              </div>

              {/* Optional Notes */}
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  Reviewer Notes / Justification (optional):
                </label>
                <textarea
                  value={reviewNotes}
                  onChange={(e) => setReviewNotes(e.target.value)}
                  placeholder="e.g., Verified high expense due to approved bulk office hardware renewal."
                  rows={3}
                  className="w-full text-xs p-2.5 bg-slate-50 border border-slate-300 rounded-md focus:bg-white focus:outline-hidden focus:ring-1 focus:ring-teal-600 text-slate-900"
                />
              </div>
            </div>

            {/* Modal Footer */}
            <div className="px-5 py-3 border-t border-slate-200 bg-slate-50 flex items-center justify-between gap-3">
              {reviewingItem.is_reviewed ? (
                <button
                  type="button"
                  onClick={handleResetReview}
                  disabled={isSubmittingReview}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs text-rose-700 hover:bg-rose-50 border border-rose-300 rounded-md font-medium transition-colors"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Unmark Reviewed</span>
                </button>
              ) : (
                <div />
              )}

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setReviewingItem(null)}
                  className="px-3.5 py-1.5 text-xs text-slate-700 hover:bg-slate-200/70 rounded-md font-medium transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleConfirmReview}
                  disabled={isSubmittingReview}
                  className="inline-flex items-center gap-1.5 px-4 py-1.5 bg-teal-600 hover:bg-teal-700 text-white rounded-md text-xs font-medium transition-colors shadow-xs"
                >
                  {isSubmittingReview ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Check className="w-3.5 h-3.5" />
                  )}
                  <span>{reviewingItem.is_reviewed ? 'Update Review Note' : 'Confirm Audit Review'}</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
