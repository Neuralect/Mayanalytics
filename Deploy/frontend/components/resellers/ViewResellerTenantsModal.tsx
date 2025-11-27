'use client';

import { useState, useEffect } from 'react';
import { resellersApi } from '@/lib/api';
import { Reseller, Tenant } from '@/types';

interface Props {
  reseller: Reseller;
  onClose: () => void;
  onRefresh: () => void;
}

export default function ViewResellerTenantsModal({ reseller, onClose, onRefresh }: Props) {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    loadTenants();
  }, [reseller.user_id]);

  const loadTenants = async () => {
    try {
      setLoading(true);
      const response = await resellersApi.getTenants(reseller.user_id);
      setTenants(response.tenants || []);
    } catch (err: any) {
      setError(err.message || 'Errore nel caricamento dei tenant');
    } finally {
      setLoading(false);
    }
  };

  const handleRemove = async (tenantId: string, tenantName: string) => {
    if (!confirm(`Sei sicuro di voler rimuovere il tenant "${tenantName}" da questo reseller?`)) {
      return;
    }

    try {
      await resellersApi.removeTenant({
        reseller_id: reseller.user_id,
        tenant_id: tenantId,
      });
      loadTenants();
      onRefresh();
    } catch (err: any) {
      alert('Errore durante la rimozione: ' + err.message);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="card max-w-3xl w-full max-h-[90vh] overflow-y-auto">
        <h3 className="text-2xl font-semibold text-gray-800 mb-4">Tenant Assegnati al Reseller</h3>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4">
            {error}
          </div>
        )}

        {loading ? (
          <div className="text-center py-8">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600 mb-2"></div>
            <p className="text-gray-600">Caricamento tenant...</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-gray-50">
                  <th className="px-4 py-3 text-left font-semibold text-gray-800 border-b">Nome Tenant</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-800 border-b">Admin Email</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-800 border-b">Azioni</th>
                </tr>
              </thead>
              <tbody>
                {tenants.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="px-4 py-8 text-center text-gray-500">
                      Nessun tenant assegnato
                    </td>
                  </tr>
                ) : (
                  tenants.map((tenant) => (
                    <tr key={tenant.tenant_id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 border-b">{tenant.name}</td>
                      <td className="px-4 py-3 border-b">{tenant.admin_email || 'N/A'}</td>
                      <td className="px-4 py-3 border-b">
                        <button
                          onClick={() => handleRemove(tenant.tenant_id, tenant.name)}
                          className="btn btn-small btn-danger"
                        >
                          Rimuovi
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        <div className="mt-4">
          <button
            onClick={onClose}
            className="btn btn-secondary w-full"
          >
            Chiudi
          </button>
        </div>
      </div>
    </div>
  );
}

