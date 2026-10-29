import React from 'react';
import { CreditCard, Clock } from 'lucide-react';

export default function PaymentTrackerPlaceholder() {
  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-200 pb-5">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Payment Tracker</h1>
          <p className="text-sm text-slate-500 mt-1">
            Record payments and track balances.
          </p>
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded-lg p-8 shadow-xs">
        <div className="max-w-xl mx-auto text-center space-y-4">
          <div className="w-12 h-12 bg-teal-50 text-teal-600 rounded-full flex items-center justify-center mx-auto">
            <CreditCard className="w-6 h-6" />
          </div>
          <h2 className="text-lg font-semibold text-slate-900">Payment Tracker Shell</h2>
          <p className="text-sm text-slate-600 leading-relaxed">
            Recording full and partial payments, maintaining historical ledger records, and computing balances will be implemented in Stage 4.
          </p>
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-100 text-xs font-medium text-slate-600">
            <Clock className="w-3.5 h-3.5 text-teal-600" />
            <span>Scheduled for Stage 4: Payment Tracker & Balance Engine</span>
          </div>
        </div>
      </div>
    </div>
  );
}
