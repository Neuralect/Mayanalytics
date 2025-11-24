'use client';

import { useAuth } from '@/contexts/AuthContext';
import { getRoleBadgeClass } from '@/lib/utils';
import { useState, useEffect } from 'react';
import { tenantsApi } from '@/lib/api';
import { Tenant } from '@/types';

export default function DashboardHeader() {
  const { user, logout, selectedTenantId, setSelectedTenantId, setShowContextSelector } = useAuth();
  const [currentTenant, setCurrentTenant] = useState<Tenant | null>(null);
  const [loadingTenant, setLoadingTenant] = useState(false);

  useEffect(() => {
    if (selectedTenantId) {
      loadTenantInfo();
    } else {
      setCurrentTenant(null);
    }
  }, [selectedTenantId]);

  const loadTenantInfo = async () => {
    if (!selectedTenantId) return;
    try {
      setLoadingTenant(true);
      const response = await tenantsApi.get(selectedTenantId);
      if (response.tenant) {
        setCurrentTenant(response.tenant);
      }
    } catch (error) {
      console.error('Error loading tenant info:', error);
    } finally {
      setLoadingTenant(false);
    }
  };

  const handleBackToGlobal = () => {
    setSelectedTenantId(null);
  };

  const handleChangeContext = () => {
    setShowContextSelector(true);
  };

  if (!user) return null;

  const isSuperAdminOrReseller = user.role === 'SuperAdmin' || user.role === 'Reseller';

  return (
    <div className="card mb-6">
      <div className="flex flex-col md:flex-row justify-between items-center gap-4">
        <div className="flex items-center gap-4">
          <h2 className="text-3xl font-semibold text-gray-800">Maya Analytics</h2>
          {selectedTenantId && currentTenant && (
            <div className="flex items-center gap-2">
              <span className="text-gray-400">→</span>
              <span className="text-lg font-semibold text-purple-600">{currentTenant.name}</span>
            </div>
          )}
        </div>
        
        <div className="flex items-center gap-4">
          <div className="text-right">
            <div className="font-semibold text-gray-800">{user.name || 'User'}</div>
            <div className="text-sm text-gray-600">{user.email}</div>
          </div>
          
          <span className={`badge ${getRoleBadgeClass(user.role)}`}>
            {user.role}
          </span>

          {isSuperAdminOrReseller && (
            <>
              {selectedTenantId ? (
                <button
                  onClick={handleBackToGlobal}
                  className="btn btn-secondary btn-small"
                  title="Torna alla Dashboard Globale"
                >
                  ← Dashboard Globale
                </button>
              ) : (
                <button
                  onClick={handleChangeContext}
                  className="btn btn-secondary btn-small"
                  title="Cambia Contesto"
                >
                  Cambia Contesto
                </button>
              )}
            </>
          )}
          
          <button
            onClick={logout}
            className="btn btn-danger btn-small"
          >
            Logout
          </button>
        </div>
      </div>
    </div>
  );
}

