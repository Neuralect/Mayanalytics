'use client';

import { useAuth } from '@/contexts/AuthContext';
import LoginForm from '@/components/LoginForm';
import ChangePasswordForm from '@/components/ChangePasswordForm';
import ForgotPasswordForm from '@/components/ForgotPasswordForm';
import ResetPasswordForm from '@/components/ResetPasswordForm';
import Dashboard from '@/components/Dashboard';
import ContextSelector from '@/components/ContextSelector';
import { useEffect, useState } from 'react';
import { CognitoUser } from 'amazon-cognito-identity-js';

type PasswordResetState = 'login' | 'forgot-password' | 'reset-password';

export default function Home() {
  const { user, loading, requiresPasswordChange, showContextSelector, setShowContextSelector } = useAuth();
  const [passwordResetState, setPasswordResetState] = useState<PasswordResetState>('login');
  const [resetEmail, setResetEmail] = useState('');
  const [resetCognitoUser, setResetCognitoUser] = useState<CognitoUser | null>(null);

  // Reset password reset state when user logs out
  useEffect(() => {
    if (!user && !loading) {
      // Reset password reset state when user logs out
      setPasswordResetState('login');
      setResetEmail('');
      setResetCognitoUser(null);
    }
  }, [user, loading]);

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
    // Gestione reset password
    if (passwordResetState === 'forgot-password') {
      return (
        <ForgotPasswordForm
          onBack={() => setPasswordResetState('login')}
          onCodeSent={(email, cognitoUser) => {
            setResetEmail(email);
            setResetCognitoUser(cognitoUser);
            setPasswordResetState('reset-password');
          }}
        />
      );
    }

    if (passwordResetState === 'reset-password' && resetCognitoUser) {
      return (
        <ResetPasswordForm
          email={resetEmail}
          cognitoUser={resetCognitoUser}
          onBack={() => setPasswordResetState('forgot-password')}
          onSuccess={() => {
            setPasswordResetState('login');
            setResetEmail('');
            setResetCognitoUser(null);
          }}
        />
      );
    }

    return (
      <LoginForm
        onForgotPassword={() => setPasswordResetState('forgot-password')}
      />
    );
  }

  if (showContextSelector && (user.role === 'SuperAdmin' || user.role === 'Reseller')) {
    return <ContextSelector />;
  }

  return <Dashboard />;
}
