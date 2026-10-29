import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, Link } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import PublicRoute from './components/PublicRoute';
import Layout from './components/Layout';

import Login from './pages/Login';
import Signup from './pages/Signup';
import Dashboard from './pages/Dashboard';
import Invoices from './pages/Invoices';
import PaymentTracker from './pages/PaymentTracker';
import PaymentDeadlines from './pages/PaymentDeadlines';
import Reconciliation from './pages/Reconciliation';
import AnomalyDetection from './pages/AnomalyDetection';
import Reports from './pages/Reports';

function NotFound() {
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-4 text-center">
      <h1 className="text-4xl font-bold text-slate-900 mb-2">404</h1>
      <p className="text-slate-600 mb-6 text-sm">The page you requested could not be found.</p>
      <Link
        to="/dashboard"
        className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-md text-sm font-medium transition-colors shadow-xs"
      >
        Return to Dashboard
      </Link>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public Authentication Routes */}
          <Route element={<PublicRoute />}>
            <Route path="/login" element={<Login />} />
            <Route path="/signup" element={<Signup />} />
          </Route>

          {/* Authenticated Protected Routes */}
          <Route element={<ProtectedRoute />}>
            <Route element={<Layout />}>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/invoices" element={<Invoices />} />
              <Route path="/payments" element={<PaymentTracker />} />
              <Route path="/deadlines" element={<PaymentDeadlines />} />
              <Route path="/reconciliation" element={<Reconciliation />} />
              <Route path="/anomalies" element={<AnomalyDetection />} />
              <Route path="/reports" element={<Reports />} />
            </Route>
          </Route>

          {/* Catch-all 404 Route */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
