'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { tenantsApi, resellersApi } from '@/lib/api';
import { Tenant } from '@/types';

export default function ContextSelector() {
  const { user, setSelectedTenantId, setShowContextSelector } = useAuth();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (user) {
      loadTenants();
    }
  }, [user]);

  const loadTenants = async () => {
    try {
      setLoading(true);
      const response = await tenantsApi.list();
      setTenants(response.tenants || []);
    } catch (error) {
      console.error('Error loading tenants:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectGlobal = () => {
    setSelectedTenantId(null);
    setShowContextSelector(false);
  };

  const handleSelectTenant = (tenantId: string) => {
    setSelectedTenantId(tenantId);
    setShowContextSelector(false);
  };

  if (!user || (user.role !== 'SuperAdmin' && user.role !== 'Reseller')) {
    return null;
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-5">
      <div className="max-w-2xl w-full">
        <div className="card">
          <h2 className="text-3xl font-semibold text-gray-800 mb-6 text-center">
            Seleziona Contesto
          </h2>
          
          <div className="space-y-4">
            <button
              onClick={handleSelectGlobal}
              className="w-full p-6 text-left border-2 border-purple-500 rounded-lg hover:bg-purple-50 transition-colors"
            >
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-xl font-semibold text-gray-800 mb-2">
                    Dashboard {user.role}
                  </h3>
                  <p className="text-gray-600">
                    Gestione globale: reseller, tenant e utenti
                  </p>
                </div>
                <div className="text-purple-600 text-2xl">→</div>
              </div>
            </button>

            <div className="border-t pt-4">
              <h3 className="text-lg font-semibold text-gray-800 mb-4">
                Oppure entra in un Tenant:
              </h3>
              
              {loading ? (
                <div className="text-center py-8">
                  <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600"></div>
                  <p className="text-gray-600 mt-2">Caricamento tenant...</p>
                </div>
              ) : tenants.length === 0 ? (
                <p className="text-gray-500 text-center py-4">
                  Nessun tenant disponibile
                </p>
              ) : (
                <div className="space-y-2">
                  {tenants.map((tenant) => (
                    <button
                      key={tenant.tenant_id}
                      onClick={() => handleSelectTenant(tenant.tenant_id)}
                      className="w-full p-4 text-left border border-gray-300 rounded-lg hover:bg-gray-50 hover:border-purple-500 transition-colors"
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <h4 className="font-semibold text-gray-800">
                            {tenant.name}
                          </h4>
                          <p className="text-sm text-gray-600">
                            {tenant.tenant_id}
                          </p>
                        </div>
                        <div className="text-purple-600">→</div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

