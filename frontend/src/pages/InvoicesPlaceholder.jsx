import React from 'react';
import { FileText, Clock } from 'lucide-react';

export default function InvoicesPlaceholder() {
  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-200 pb-5">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Invoices</h1>
          <p className="text-sm text-slate-500 mt-1">
            Manage, upload, and review invoices.
          </p>
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded-lg p-8 shadow-xs">
        <div className="max-w-xl mx-auto text-center space-y-4">
          <div className="w-12 h-12 bg-teal-50 text-teal-600 rounded-full flex items-center justify-center mx-auto">
            <FileText className="w-6 h-6" />
          </div>
          <h2 className="text-lg font-semibold text-slate-900">Invoice Management Shell</h2>
          <p className="text-sm text-slate-600 leading-relaxed">
            Invoice upload (PDF/images), automated field extraction, human review modal, and CRUD records will be implemented next in Stage 3.
          </p>
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-100 text-xs font-medium text-slate-600">
            <Clock className="w-3.5 h-3.5 text-teal-600" />
            <span>Scheduled for Stage 3: Invoice Models & Extraction</span>
          </div>
        </div>
      </div>
    </div>
  );
}
