'use client';

import { useState, useMemo } from 'react';
import { Tenant } from '@/types';
import { tenantsApi } from '@/lib/api';
import { useAuth } from '@/contexts/AuthContext';
import { useRouter } from 'next/navigation';
import CreateTenantModal from './CreateTenantModal';
import CreateTenantAdminModal from './CreateTenantAdminModal';
import SearchAndFilter from '../common/SearchAndFilter';

interface Props {
  tenants: Tenant[];
  onRefresh: () => void;
  canCreate: boolean;
}

export default function TenantManagement({ tenants, onRefresh, canCreate }: Props) {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showCreateAdminModal, setShowCreateAdminModal] = useState(false);
  const [selectedTenantForAdmin, setSelectedTenantForAdmin] = useState<Tenant | null>(null);
  const { setSelectedTenantId } = useAuth();
  const router = useRouter();
  const [searchTerm, setSearchTerm] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [filterStatus, setFilterStatus] = useState('all');
  const [filterDateRange, setFilterDateRange] = useState('all');

  const handleEnterTenant = (tenantId: string) => {
    setSelectedTenantId(tenantId);
    router.push('/dashboard');
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

  const handleCreateAdmin = (tenant: Tenant) => {
    setSelectedTenantForAdmin(tenant);
    setShowCreateAdminModal(true);
  };

  const handleCreateAdminSuccess = () => {
    setShowCreateAdminModal(false);
    setSelectedTenantForAdmin(null);
    onRefresh();
  };

  // Filter and search logic
  const filteredTenants = useMemo(() => {
    let filtered = [...tenants];

    // Apply search filter
    if (searchTerm.trim()) {
      const searchLower = searchTerm.toLowerCase();
      filtered = filtered.filter(
        (tenant) =>
          tenant.name.toLowerCase().includes(searchLower) ||
          tenant.admin_email?.toLowerCase().includes(searchLower) ||
          tenant.admin_name?.toLowerCase().includes(searchLower)
      );
    }

    // Apply status filter
    if (filterStatus !== 'all') {
      filtered = filtered.filter((tenant) => {
        const status = tenant.status || 'ACTIVE';
        return status.toLowerCase() === filterStatus.toLowerCase();
      });
    }

    // Apply date range filter
    if (filterDateRange !== 'all' && filterDateRange !== 'none') {
      const now = new Date();
      filtered = filtered.filter((tenant) => {
        if (!tenant.created_at) return false;
        
        const createdDate = new Date(tenant.created_at);
        const daysDiff = Math.floor((now.getTime() - createdDate.getTime()) / (1000 * 60 * 60 * 24));
        
        switch (filterDateRange) {
          case 'last7days':
            return daysDiff <= 7;
          case 'last30days':
            return daysDiff <= 30;
          case 'last90days':
            return daysDiff <= 90;
          case 'last6months':
            return daysDiff <= 180;
          case 'lastyear':
            return daysDiff <= 365;
          case 'older':
            return daysDiff > 365;
          default:
            return true;
        }
      });
    } else if (filterDateRange === 'none') {
      // Filter out tenants without created_at
      filtered = filtered.filter((tenant) => !tenant.created_at);
    }

    return filtered;
  }, [tenants, searchTerm, filterStatus, filterDateRange]);

  return (
    <>
      <div className="card">
        <div className="content-card">
          <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3 mb-4">
            <h3 className="text-xl sm:text-2xl font-semibold text-gray-800">Gestione Tenant</h3>
            {canCreate && (
            <button
              onClick={() => setShowCreateModal(true)}
              className="btn bg-[#286291] hover:bg-[#113357] text-white w-full sm:w-auto text-sm sm:text-base whitespace-nowrap"
            >
              + Crea Nuovo Tenant
            </button>
            )}
          </div>

          <SearchAndFilter
            searchPlaceholder="Cerca per nome tenant, admin email o nome admin..."
            searchValue={searchTerm}
            onSearchChange={setSearchTerm}
            showFilters={showFilters}
            onToggleFilters={() => setShowFilters(!showFilters)}
            filters={[
              {
                label: 'Stato',
                key: 'status',
                value: filterStatus,
                onChange: setFilterStatus,
                options: [
                  { label: 'Tutti', value: 'all' },
                  { label: 'Attivo', value: 'active' },
                  { label: 'Inattivo', value: 'inactive' },
                ],
              },
              {
                label: 'Data Creazione',
                key: 'dateRange',
                value: filterDateRange,
                onChange: setFilterDateRange,
                options: [
                  { label: 'Tutti', value: 'all' },
                  { label: 'Ultimi 7 giorni', value: 'last7days' },
                  { label: 'Ultimi 30 giorni', value: 'last30days' },
                  { label: 'Ultimi 90 giorni', value: 'last90days' },
                  { label: 'Ultimi 6 mesi', value: 'last6months' },
                  { label: 'Ultimo anno', value: 'lastyear' },
                  { label: 'Più vecchi di 1 anno', value: 'older' },
                  { label: 'Senza data', value: 'none' },
                ],
              },
            ]}
          />

          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr>
                  <th className="px-4 py-3 text-left font-semibold text-gray-800">Nome Tenant</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-800">Admin Email</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-800">Stato</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-800">Azioni</th>
                </tr>
              </thead>
              <tbody>
                {filteredTenants.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-gray-500">
                      {tenants.length === 0
                        ? 'Nessun tenant trovato'
                        : 'Nessun tenant corrisponde ai filtri selezionati'}
                    </td>
                  </tr>
                ) : (
                  filteredTenants.map((tenant) => (
                    <tr key={tenant.tenant_id}>
                      <td className="px-4 py-3 text-gray-800">{tenant.name}</td>
                      <td className="px-4 py-3 text-gray-800">{tenant.admin_email || 'N/A'}</td>
                      <td className="px-4 py-3">
                        <span className="badge bg-green-100 text-green-800">
                          {tenant.status || 'ATTIVO'}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleEnterTenant(tenant.tenant_id)}
                            className="btn btn-small bg-[#286291] hover:bg-[#113357] text-white"
                          >
                            Entra
                          </button>
                        {canCreate && !tenant.admin_email && (
                          <button
                            onClick={() => handleCreateAdmin(tenant)}
                            className="btn btn-small bg-[#286291] hover:bg-[#113357] text-white"
                            title="Crea Admin per questo tenant"
                          >
                            Crea Admin
                          </button>
                        )}
                        {canCreate && (
                          <button
                            onClick={() => handleDelete(tenant.tenant_id)}
                            className="btn btn-small bg-[#286291] hover:bg-[#113357] text-white"
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

      {showCreateAdminModal && selectedTenantForAdmin && (
        <CreateTenantAdminModal
          tenantId={selectedTenantForAdmin.tenant_id}
          tenantName={selectedTenantForAdmin.name}
          onClose={() => {
            setShowCreateAdminModal(false);
            setSelectedTenantForAdmin(null);
          }}
          onSuccess={handleCreateAdminSuccess}
        />
      )}
    </>
  );
}

