'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { tenantsApi, resellersApi } from '@/lib/api';
import { Tenant } from '@/types';
import { useRouter } from 'next/navigation';
import Image from 'next/image';

export default function ContextSelector() {
  const { user, setSelectedTenantId, setShowContextSelector } = useAuth();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

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
    // Mark that context has been selected (even if global)
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('contextSelected', 'true');
    }
    setShowContextSelector(false);
    router.push('/dashboard');
  };

  const handleSelectTenant = (tenantId: string) => {
    setSelectedTenantId(tenantId);
    // Mark that context has been selected
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('contextSelected', 'true');
    }
    setShowContextSelector(false);
    router.push('/dashboard');
  };

  if (!user || (user.role !== 'SuperAdmin' && user.role !== 'Reseller')) {
    return null;
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-[#eeeeee]">
      <div className="w-full max-w-2xl bg-white rounded-lg shadow-2xl p-8">
        <div className="text-center mb-8">
          <div className="flex justify-center mb-6">
            <Image
              src="/images/logo.svg"
              alt="Logo"
              width={300}
              height={300}
              className="object-contain"
              priority
            />
          </div>
          <h2 className="text-3xl font-semibold text-gray-800 mb-6">
            Seleziona Contesto
          </h2>
        </div>
        
        <div className="space-y-4">
          <button
            onClick={handleSelectGlobal}
            className="w-full p-6 text-left border-2 border-[#286291] rounded-lg hover:bg-[#eeeeee] transition-colors bg-white"
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
              <div className="text-[#286291] text-2xl">→</div>
            </div>
          </button>

          <div className="border-t border-gray-300 pt-4">
            <h3 className="text-lg font-semibold text-gray-800 mb-4">
              Oppure entra in un Tenant:
            </h3>
            
            {loading ? (
              <div className="text-center py-8">
                <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-[#286291]"></div>
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
                    className="w-full p-4 text-left border border-gray-300 rounded-lg hover:bg-gray-50 hover:border-[#286291] transition-colors bg-white"
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
                      <div className="text-[#286291]">→</div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

