import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Eye, EyeOff, Loader2, AlertCircle, CheckCircle2 } from 'lucide-react';

export default function Signup() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { signup } = useAuth();
  const navigate = useNavigate();

  const validateForm = () => {
    const trimmedName = name.trim();
    if (!trimmedName || trimmedName.length < 2) {
      setErrorMessage('Full name must be at least 2 characters long.');
      return false;
    }

    const trimmedEmail = email.trim().toLowerCase();
    const emailRegex = /^[\w.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/;
    if (!trimmedEmail || !emailRegex.test(trimmedEmail)) {
      setErrorMessage('Please enter a valid email address (e.g. name@company.com).');
      return false;
    }

    if (!password || password.length < 8) {
      setErrorMessage('Password must be at least 8 characters long.');
      return false;
    }

    if (password !== confirmPassword) {
      setErrorMessage('Passwords do not match. Please re-enter matching passwords.');
      return false;
    }

    return true;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage('');
    setSuccessMessage('');

    if (!validateForm()) {
      return;
    }

    setIsSubmitting(true);
    try {
      await signup(name.trim(), email.trim(), password);
      setSuccessMessage('Account created successfully! Redirecting to your dashboard...');
      setTimeout(() => {
        navigate('/dashboard', { replace: true });
      }, 1000);
    } catch (err) {
      setErrorMessage(err.message || 'Registration failed. Please check your details and try again.');
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
          Create your account
        </h2>
        <p className="mt-1 text-xs text-slate-500">
          Get started with modern financial tracking
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

          {/* Success Banner */}
          {successMessage && (
            <div className="mb-5 flex items-start gap-3 p-3 text-sm text-teal-800 bg-teal-50 border border-teal-200 rounded-md">
              <CheckCircle2 className="w-5 h-5 shrink-0 text-teal-600 mt-0.5" />
              <div className="flex-1">{successMessage}</div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            {/* Full Name */}
            <div>
              <label
                htmlFor="name"
                className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5"
              >
                Full Name
              </label>
              <input
                id="name"
                name="name"
                type="text"
                required
                autoFocus
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Jane Doe"
                disabled={isSubmitting}
                className="w-full px-3.5 py-2.5 text-sm bg-white border border-slate-300 rounded-md text-slate-900 placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-teal-600 focus:border-teal-600 transition-colors disabled:bg-slate-100 disabled:cursor-not-allowed"
              />
            </div>

            {/* Email Address */}
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
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@company.com"
                disabled={isSubmitting}
                className="w-full px-3.5 py-2.5 text-sm bg-white border border-slate-300 rounded-md text-slate-900 placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-teal-600 focus:border-teal-600 transition-colors disabled:bg-slate-100 disabled:cursor-not-allowed"
              />
            </div>

            {/* Password */}
            <div>
              <label
                htmlFor="password"
                className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5"
              >
                Password <span className="text-slate-400 font-normal lowercase">(min 8 characters)</span>
              </label>
              <div className="relative">
                <input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Create a strong password"
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

            {/* Confirm Password */}
            <div>
              <label
                htmlFor="confirmPassword"
                className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5"
              >
                Confirm Password
              </label>
              <div className="relative">
                <input
                  id="confirmPassword"
                  name="confirmPassword"
                  type={showConfirmPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Repeat your password"
                  disabled={isSubmitting}
                  className="w-full px-3.5 py-2.5 pr-10 text-sm bg-white border border-slate-300 rounded-md text-slate-900 placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-teal-600 focus:border-teal-600 transition-colors disabled:bg-slate-100 disabled:cursor-not-allowed"
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-600 focus:outline-hidden"
                  tabIndex={-1}
                  aria-label={showConfirmPassword ? 'Hide confirm password' : 'Show confirm password'}
                >
                  {showConfirmPassword ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>

            {/* Submit Button */}
            <div className="pt-2">
              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-md text-sm font-medium text-white bg-teal-600 hover:bg-teal-700 focus:outline-hidden focus:ring-2 focus:ring-teal-500 focus:ring-offset-2 transition-colors disabled:opacity-70 disabled:cursor-not-allowed shadow-xs"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Creating account...</span>
                  </>
                ) : (
                  <span>Create account</span>
                )}
              </button>
            </div>
          </form>

          {/* Footer Navigation Link */}
          <div className="mt-6 pt-5 border-t border-slate-100 text-center">
            <p className="text-xs text-slate-500">
              Already have an account?{' '}
              <Link
                to="/login"
                className="font-medium text-teal-600 hover:text-teal-700 hover:underline"
              >
                Sign in
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
