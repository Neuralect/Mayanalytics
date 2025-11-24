'use client';

// ========================================
// AUTH CONTEXT
// ========================================

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { CognitoUser, AuthenticationDetails } from 'amazon-cognito-identity-js';
import { userPool } from '@/lib/cognito';
import { profileApi } from '@/lib/api';
import { User } from '@/types';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  changePassword: (newPassword: string) => Promise<void>;
  refreshUser: () => Promise<void>;
  requiresPasswordChange: boolean;
  setRequiresPasswordChange: (value: boolean) => void;
  currentCognitoUser: CognitoUser | null;
  setCurrentCognitoUser: (user: CognitoUser | null) => void;
  selectedTenantId: string | null;
  setSelectedTenantId: (tenantId: string | null) => void;
  showContextSelector: boolean;
  setShowContextSelector: (show: boolean) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [requiresPasswordChange, setRequiresPasswordChange] = useState(false);
  const [currentCognitoUser, setCurrentCognitoUser] = useState<CognitoUser | null>(null);
  const [selectedTenantId, setSelectedTenantIdState] = useState<string | null>(null);
  const [showContextSelector, setShowContextSelector] = useState(false);

  // Load selected tenant from sessionStorage on mount
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const savedTenantId = sessionStorage.getItem('selectedTenantId');
      if (savedTenantId) {
        setSelectedTenantIdState(savedTenantId);
      }
    }
  }, []);

  const setSelectedTenantId = (tenantId: string | null) => {
    setSelectedTenantIdState(tenantId);
    if (typeof window !== 'undefined') {
      if (tenantId) {
        sessionStorage.setItem('selectedTenantId', tenantId);
      } else {
        sessionStorage.removeItem('selectedTenantId');
      }
    }
  };

  const loadUserProfile = useCallback(async (token: string) => {
    try {
      // Store token for API calls
      if (typeof window !== 'undefined') {
        localStorage.setItem('cognito_id_token', token);
      }

      const response = await profileApi.get();
      if (response.user) {
        setUser(response.user);
      }
    } catch (error) {
      console.error('Error loading user profile:', error);
      throw error;
    }
  }, []);

  const checkAuthState = useCallback(async () => {
    try {
      const cognitoUser = userPool.getCurrentUser();
      
      if (cognitoUser) {
        cognitoUser.getSession((err: Error | null, session: any) => {
          if (err || !session.isValid()) {
            setLoading(false);
            return;
          }
          
          const token = session.getIdToken().getJwtToken();
          loadUserProfile(token)
            .then(() => setLoading(false))
            .catch(() => setLoading(false));
        });
      } else {
        setLoading(false);
      }
    } catch (error) {
      console.error('Error checking auth state:', error);
      setLoading(false);
    }
  }, [loadUserProfile]);

  useEffect(() => {
    checkAuthState();
  }, [checkAuthState]);

  const login = async (email: string, password: string) => {
    return new Promise<void>((resolve, reject) => {
      const authData = {
        Username: email,
        Password: password,
      };
      
      const authDetails = new AuthenticationDetails(authData);
      const userData = { Username: email, Pool: userPool };
      const cognitoUser = new CognitoUser(userData);
      
      cognitoUser.authenticateUser(authDetails, {
        onSuccess: async (session) => {
          const token = session.getIdToken().getJwtToken();
          setCurrentCognitoUser(cognitoUser);
          try {
            await loadUserProfile(token);
            resolve();
          } catch (error) {
            reject(error);
          }
        },
        onFailure: (error) => {
          reject(error);
        },
        newPasswordRequired: () => {
          setCurrentCognitoUser(cognitoUser);
          setRequiresPasswordChange(true);
          resolve();
        },
      });
    });
  };

  const changePassword = async (newPassword: string) => {
    return new Promise<void>((resolve, reject) => {
      if (!currentCognitoUser) {
        reject(new Error('No user session'));
        return;
      }

      currentCognitoUser.completeNewPasswordChallenge(newPassword, {}, {
        onSuccess: async (session) => {
          const token = session.getIdToken().getJwtToken();
          setRequiresPasswordChange(false);
          try {
            await loadUserProfile(token);
            resolve();
          } catch (error) {
            reject(error);
          }
        },
        onFailure: reject,
      });
    });
  };

  const logout = () => {
    const cognitoUser = userPool.getCurrentUser();
    if (cognitoUser) {
      cognitoUser.signOut();
    }
    if (typeof window !== 'undefined') {
      localStorage.removeItem('cognito_id_token');
      sessionStorage.removeItem('selectedTenantId');
    }
    setUser(null);
    setCurrentCognitoUser(null);
    setRequiresPasswordChange(false);
    setSelectedTenantIdState(null);
    setShowContextSelector(false);
  };

  const refreshUser = async () => {
    const cognitoUser = userPool.getCurrentUser();
    if (cognitoUser) {
      cognitoUser.getSession((err: Error | null, session: any) => {
        if (!err && session.isValid()) {
          const token = session.getIdToken().getJwtToken();
          loadUserProfile(token);
        }
      });
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        logout,
        changePassword,
        refreshUser,
        requiresPasswordChange,
        setRequiresPasswordChange,
        currentCognitoUser,
        setCurrentCognitoUser,
        selectedTenantId,
        setSelectedTenantId,
        showContextSelector,
        setShowContextSelector,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

