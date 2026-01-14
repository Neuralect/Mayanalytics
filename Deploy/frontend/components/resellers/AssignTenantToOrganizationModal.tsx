'use client';

import { useState } from 'react';
import { resellerOrganizationsApi } from '@/lib/api';
import { ResellerOrganization, Tenant, AssignTenantToOrganizationInput } from '@/types';

interface Props {
  organization: ResellerOrganization;
  tenants: Tenant[];
  onClose: () => void;
  onSuccess: () => void;
}

export default function AssignTenantToOrganizationModal({ organization, tenants, onClose, onSuccess }: Props) {
  const [selectedTenantId, setSelectedTenantId] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Filter out already assigned tenants
  const assignedTenantIds = organization.tenants || [];
  const availableTenants = tenants.filter(t => !assignedTenantIds.includes(t.tenant_id));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTenantId) {
      setError('Seleziona un tenant');
      return;
    }

    setError('');
    setLoading(true);

    try {
      const data: AssignTenantToOrganizationInput = { tenant_id: selectedTenantId };
      await resellerOrganizationsApi.assignTenant(organization.org_id, data);
      onSuccess();
    } catch (err: any) {
      setError(err.message || 'Errore nell\'assegnazione del tenant');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 modal-backdrop flex items-center justify-center z-50 p-4">
      <div className="card max-w-md w-full max-h-[90vh] overflow-y-auto">
        <h3 className="text-2xl font-semibold text-gray-800 mb-4">
          Assegna Tenant a {organization.name}
        </h3>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4">
            {error}
          </div>
        )}

        {availableTenants.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <p>Tutti i tenant sono già assegnati a questa organizzazione</p>
            <button
              onClick={onClose}
              className="btn btn-secondary mt-4"
            >
              Chiudi
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
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
                {availableTenants.map((tenant) => (
                  <option key={tenant.tenant_id} value={tenant.tenant_id}>
                    {tenant.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex gap-2">
              <button
                type="submit"
                disabled={loading || !selectedTenantId}
                className="btn bg-[#286291] hover:bg-[#113357] text-white flex-1"
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
        )}
      </div>
    </div>
  );
}

