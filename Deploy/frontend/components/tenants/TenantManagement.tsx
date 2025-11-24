'use client';

import { useState } from 'react';
import { Tenant } from '@/types';
import { tenantsApi } from '@/lib/api';
import { useAuth } from '@/contexts/AuthContext';
import CreateTenantModal from './CreateTenantModal';

interface Props {
  tenants: Tenant[];
  onRefresh: () => void;
  canCreate: boolean;
}

export default function TenantManagement({ tenants, onRefresh, canCreate }: Props) {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const { setSelectedTenantId } = useAuth();

  const handleEnterTenant = (tenantId: string) => {
    setSelectedTenantId(tenantId);
  };

  const handleDelete = async (tenantId: string) => {
    if (!confirm('Sei sicuro di voler eliminare questo tenant?')) {
      return;
    }

    try {
      await tenantsApi.delete(tenantId);
      onRefresh();
    } catch (err: any) {
      alert('Errore durante l\'eliminazione: ' + err.message);
    }
  };

  return (
    <>
      <div className="card">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-2xl font-semibold text-gray-800">Gestione Tenant</h3>
          {canCreate && (
            <button
              onClick={() => setShowCreateModal(true)}
              className="btn btn-primary"
            >
              + Crea Nuovo Tenant
            </button>
          )}
        </div>

        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-gray-50">
                <th className="px-4 py-3 text-left font-semibold text-gray-800 border-b">Nome Tenant</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-800 border-b">Admin Email</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-800 border-b">Stato</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-800 border-b">Azioni</th>
              </tr>
            </thead>
            <tbody>
              {tenants.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-gray-500">
                    Nessun tenant trovato
                  </td>
                </tr>
              ) : (
                tenants.map((tenant) => (
                  <tr key={tenant.tenant_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 border-b">{tenant.name}</td>
                    <td className="px-4 py-3 border-b">{tenant.admin_email}</td>
                    <td className="px-4 py-3 border-b">
                      <span className="badge bg-green-100 text-green-800">ATTIVO</span>
                    </td>
                    <td className="px-4 py-3 border-b">
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleEnterTenant(tenant.tenant_id)}
                          className="btn btn-small btn-primary"
                        >
                          Entra
                        </button>
                        {canCreate && (
                          <button
                            onClick={() => handleDelete(tenant.tenant_id)}
                            className="btn btn-small btn-danger"
                          >
                            Elimina
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {showCreateModal && (
        <CreateTenantModal
          onClose={() => setShowCreateModal(false)}
          onSuccess={() => {
            setShowCreateModal(false);
            onRefresh();
          }}
        />
      )}
    </>
  );
}

