'use client';

import { useState } from 'react';
import { resellersApi } from '@/lib/api';
import { Reseller, Tenant } from '@/types';

interface Props {
  reseller: Reseller;
  tenants: Tenant[];
  onClose: () => void;
  onSuccess: () => void;
}

export default function AssignTenantModal({ reseller, tenants, onClose, onSuccess }: Props) {
  const [selectedTenantId, setSelectedTenantId] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTenantId) {
      setError('Seleziona un tenant');
      return;
    }

    setError('');
    setLoading(true);

    try {
      await resellersApi.assignTenant({
        reseller_id: reseller.user_id,
        tenant_id: selectedTenantId,
      });
      onSuccess();
    } catch (err: any) {
      setError(err.message || 'Errore nell\'assegnazione del tenant');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="card max-w-md w-full">
        <h3 className="text-2xl font-semibold text-gray-800 mb-4">Assegna Tenant a Reseller</h3>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="block text-gray-700 font-medium mb-2">Reseller</label>
            <input
              type="text"
              value={reseller.name || reseller.email}
              disabled
              className="input bg-gray-100"
            />
          </div>

          <div className="mb-4">
            <label className="block text-gray-700 font-medium mb-2">Seleziona Tenant</label>
            <select
              value={selectedTenantId}
              onChange={(e) => setSelectedTenantId(e.target.value)}
              required
              className="input"
              disabled={loading}
            >
              <option value="">-- Seleziona un tenant --</option>
              {tenants.map((tenant) => (
                <option key={tenant.tenant_id} value={tenant.tenant_id}>
                  {tenant.name} ({tenant.admin_email})
                </option>
              ))}
            </select>
          </div>

          <div className="flex gap-2">
            <button
              type="submit"
              disabled={loading}
              className="btn btn-primary flex-1"
            >
              {loading ? 'Assegnazione in corso...' : 'Assegna Tenant'}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="btn btn-secondary"
              disabled={loading}
            >
              Annulla
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

