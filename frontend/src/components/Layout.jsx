import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import { Menu, X } from 'lucide-react';

export default function Layout() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <div className="min-h-screen flex bg-slate-50 text-slate-900">
      {/* Desktop Sidebar (hidden on mobile, visible on md and up) */}
      <div className="hidden md:flex md:w-64 md:flex-col md:fixed md:inset-y-0 z-30">
        <Sidebar />
      </div>

      {/* Mobile Drawer Overlay */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs transition-opacity"
            onClick={() => setMobileMenuOpen(false)}
          />
          {/* Drawer content */}
          <div className="fixed inset-y-0 left-0 flex flex-col z-50 w-64 bg-white shadow-xl">
            <div className="absolute top-3 right-3">
              <button
                type="button"
                onClick={() => setMobileMenuOpen(false)}
                className="p-1.5 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-100"
                aria-label="Close menu"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <Sidebar onCloseMobile={() => setMobileMenuOpen(false)} />
          </div>
        </div>
      )}

      {/* Main Page Content */}
      <div className="flex-1 flex flex-col md:pl-64">
        {/* Mobile Header Bar */}
        <header className="h-16 md:hidden flex items-center justify-between px-4 bg-white border-b border-slate-200 sticky top-0 z-20">
          <div className="flex items-center space-x-2">
            <div className="w-7 h-7 rounded bg-teal-600 flex items-center justify-center text-white font-bold text-xs tracking-tight">
              IQ
            </div>
            <span className="text-base font-bold text-slate-900 tracking-tight">
              Invoice<span className="text-teal-600">IQ</span>
            </span>
          </div>

          <button
            type="button"
            onClick={() => setMobileMenuOpen(true)}
            className="p-2 rounded-md text-slate-600 hover:text-slate-900 hover:bg-slate-100"
            aria-label="Open menu"
          >
            <Menu className="w-5 h-5" />
          </button>
        </header>

        {/* Content Container */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
