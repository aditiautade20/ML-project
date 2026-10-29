import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { loginApi, signupApi, getMeApi } from '../api/auth';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(() => sessionStorage.getItem('invoiceiq_token'));
  const [isLoading, setIsLoading] = useState(true);

  // Initialize and verify authentication state on mount
  const checkAuthStatus = useCallback(async () => {
    const savedToken = sessionStorage.getItem('invoiceiq_token');
    if (!savedToken) {
      setUser(null);
      setToken(null);
      setIsLoading(false);
      return;
    }

    try {
      const userData = await getMeApi(savedToken);
      setUser(userData);
      setToken(savedToken);
    } catch (err) {
      // Token is invalid, expired, or backend rejected it
      console.warn('Authentication token verification failed:', err.message);
      sessionStorage.removeItem('invoiceiq_token');
      setUser(null);
      setToken(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    checkAuthStatus();
  }, [checkAuthStatus]);

  const login = async (email, password) => {
    const data = await loginApi(email, password);
    sessionStorage.setItem('invoiceiq_token', data.access_token);
    setToken(data.access_token);
    setUser(data.user);
    return data.user;
  };

  const signup = async (name, email, password) => {
    const newUser = await signupApi(name, email, password);
    // After successful signup, immediately log the user in for seamless UX
    return login(email, password);
  };

  const logout = () => {
    sessionStorage.removeItem('invoiceiq_token');
    setUser(null);
    setToken(null);
  };

  const value = {
    user,
    token,
    isAuthenticated: Boolean(user && token),
    isLoading,
    login,
    signup,
    logout,
    refreshUser: checkAuthStatus,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
