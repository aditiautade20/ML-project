import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Eye, EyeOff, Loader2, AlertCircle, Sparkles } from 'lucide-react';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const from = location.state?.from?.pathname || '/dashboard';

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage('');

    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      setErrorMessage('Please enter your email address.');
      return;
    }

    if (!password) {
      setErrorMessage('Please enter your password.');
      return;
    }

    setIsSubmitting(true);
    try {
      await login(trimmedEmail, password);
      navigate(from, { replace: true });
    } catch (err) {
      setErrorMessage(err.message || 'Invalid email or password.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      {/* Brand Header */}
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        <div className="inline-flex items-center justify-center space-x-2 mb-2">
          <div className="w-9 h-9 rounded bg-teal-600 flex items-center justify-center text-white font-bold text-base tracking-tight shadow-xs">
            IQ
          </div>
          <span className="text-2xl font-bold text-slate-900 tracking-tight">
            Invoice<span className="text-teal-600">IQ</span>
          </span>
        </div>
        <h2 className="text-xl font-semibold text-slate-900 mt-2">
          Sign in to your account
        </h2>
        <p className="mt-1 text-xs text-slate-500">
          Professional Financial and Invoice Management
        </p>
      </div>

      {/* Form Card */}
      <div className="mt-6 sm:mx-auto sm:w-full sm:max-w-md px-4 sm:px-0">
        <div className="bg-white py-8 px-6 sm:px-10 border border-slate-200 rounded-lg shadow-xs">
          {/* Error Banner */}
          {errorMessage && (
            <div className="mb-5 flex items-start gap-3 p-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-md">
              <AlertCircle className="w-5 h-5 shrink-0 text-red-600 mt-0.5" />
              <div className="flex-1">{errorMessage}</div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5" noValidate>
            {/* Email Field */}
            <div>
              <label
                htmlFor="email"
                className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5"
              >
                Email Address
              </label>
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                required
                autoFocus
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@company.com"
                disabled={isSubmitting}
                className="w-full px-3.5 py-2.5 text-sm bg-white border border-slate-300 rounded-md text-slate-900 placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-teal-600 focus:border-teal-600 transition-colors disabled:bg-slate-100 disabled:cursor-not-allowed"
              />
            </div>

            {/* Password Field */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label
                  htmlFor="password"
                  className="block text-xs font-semibold text-slate-700 uppercase tracking-wider"
                >
                  Password
                </label>
              </div>
              <div className="relative">
                <input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  disabled={isSubmitting}
                  className="w-full px-3.5 py-2.5 pr-10 text-sm bg-white border border-slate-300 rounded-md text-slate-900 placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-teal-600 focus:border-teal-600 transition-colors disabled:bg-slate-100 disabled:cursor-not-allowed"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-600 focus:outline-hidden"
                  tabIndex={-1}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>

            {/* Submit Button */}
            <div>
              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-md text-sm font-medium text-white bg-teal-600 hover:bg-teal-700 focus:outline-hidden focus:ring-2 focus:ring-teal-500 focus:ring-offset-2 transition-colors disabled:opacity-70 disabled:cursor-not-allowed shadow-xs cursor-pointer"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Signing in...</span>
                  </>
                ) : (
                  <span>Sign in</span>
                )}
              </button>
            </div>
          </form>

          {/* Demo Showcase Quick Fill */}
          <div className="mt-4 pt-4 border-t border-slate-100">
            <button
              type="button"
              onClick={() => {
                setEmail('demo@invoiceiq.local');
                setPassword('DemoUser123!');
                setErrorMessage('');
              }}
              className="w-full flex items-center justify-center gap-2 py-2 px-3 text-xs font-medium text-teal-800 bg-teal-50 hover:bg-teal-100 border border-teal-200 rounded-md transition-colors cursor-pointer"
            >
              <Sparkles className="w-3.5 h-3.5 text-teal-600" />
              <span>Fill Demo Credentials (demo@invoiceiq.local)</span>
            </button>
          </div>

          {/* Footer Navigation Link */}
          <div className="mt-6 pt-5 border-t border-slate-100 text-center">
            <p className="text-xs text-slate-500">
              Don&apos;t have an account?{' '}
              <Link
                to="/signup"
                className="font-medium text-teal-600 hover:text-teal-700 hover:underline"
              >
                Create an account
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
