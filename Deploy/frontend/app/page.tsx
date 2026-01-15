'use client';

import { useAuth } from '@/contexts/AuthContext';
import LoginForm from '@/components/LoginForm';
import ChangePasswordForm from '@/components/ChangePasswordForm';
import ForgotPasswordForm from '@/components/ForgotPasswordForm';
import ContextSelector from '@/components/ContextSelector';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

export default function Home() {
  const { user, loading, requiresPasswordChange, showContextSelector, setShowContextSelector } = useAuth();
  const [showForgotPassword, setShowForgotPassword] = useState(false);
  const router = useRouter();

  // Show context selector after login for SuperAdmin/Reseller if not already selected
  useEffect(() => {
    if (user && !loading && !requiresPasswordChange) {
      if ((user.role === 'SuperAdmin' || user.role === 'Reseller') && !showContextSelector) {
        // Check if context has been selected (either global or tenant)
        const contextSelected = typeof window !== 'undefined' ? sessionStorage.getItem('contextSelected') : null;
        if (!contextSelected) {
          setShowContextSelector(true);
        } else {
          // Redirect to dashboard if context already selected
          router.push('/dashboard');
        }
      } else if (user && !showContextSelector) {
        // For other roles, redirect to dashboard
        router.push('/dashboard');
      }
    }
  }, [user, loading, requiresPasswordChange, showContextSelector, setShowContextSelector, router]);

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
    if (showForgotPassword) {
      return <ForgotPasswordForm onBack={() => setShowForgotPassword(false)} />;
    }
    return <LoginForm onForgotPassword={() => setShowForgotPassword(true)} />;
  }

  if (showContextSelector && (user.role === 'SuperAdmin' || user.role === 'Reseller')) {
    return <ContextSelector />;
  }

  // If user is logged in and context is selected, redirect to dashboard
  if (user && !showContextSelector) {
    router.push('/dashboard');
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-white mb-4"></div>
          <p className="text-white">Reindirizzamento...</p>
        </div>
      </div>
    );
  }

  return null;
}
