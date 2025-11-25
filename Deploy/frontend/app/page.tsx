'use client';

import { useAuth } from '@/contexts/AuthContext';
import LoginForm from '@/components/LoginForm';
import ChangePasswordForm from '@/components/ChangePasswordForm';
import Dashboard from '@/components/Dashboard';
import ContextSelector from '@/components/ContextSelector';
import { useEffect } from 'react';

export default function Home() {
  const { user, loading, requiresPasswordChange, showContextSelector, setShowContextSelector } = useAuth();

  // Show context selector after login for SuperAdmin/Reseller if not already selected
  useEffect(() => {
    if (user && !loading && !requiresPasswordChange) {
      if ((user.role === 'SuperAdmin' || user.role === 'Reseller') && !showContextSelector) {
        // Check if context has been selected (either global or tenant)
        const contextSelected = typeof window !== 'undefined' ? sessionStorage.getItem('contextSelected') : null;
        if (!contextSelected) {
          setShowContextSelector(true);
        }
      }
    }
  }, [user, loading, requiresPasswordChange, showContextSelector, setShowContextSelector]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-white mb-4"></div>
          <p className="text-white">Caricamento...</p>
        </div>
      </div>
    );
  }

  if (requiresPasswordChange) {
    return <ChangePasswordForm />;
  }

  if (!user) {
    return <LoginForm />;
  }

  if (showContextSelector && (user.role === 'SuperAdmin' || user.role === 'Reseller')) {
    return <ContextSelector />;
  }

  return <Dashboard />;
}
