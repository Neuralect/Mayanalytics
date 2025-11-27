'use client';

import { useState, useMemo } from 'react';
import { Reseller, Tenant } from '@/types';
import { resellersApi } from '@/lib/api';
import CreateResellerModal from './CreateResellerModal';
import AssignTenantModal from './AssignTenantModal';
import ViewResellerTenantsModal from './ViewResellerTenantsModal';
import SearchAndFilter from '../common/SearchAndFilter';

interface Props {
  resellers: Reseller[];
  tenants: Tenant[];
  onRefresh: () => void;
}

export default function ResellerManagement({ resellers, tenants, onRefresh }: Props) {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showAssignModal, setShowAssignModal] = useState(false);
  const [showViewModal, setShowViewModal] = useState(false);
  const [selectedReseller, setSelectedReseller] = useState<Reseller | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [filterTenantsCount, setFilterTenantsCount] = useState('all');
  const [filterDateRange, setFilterDateRange] = useState('all');

  const handleCreateSuccess = () => {
    setShowCreateModal(false);
    onRefresh();
  };

  const handleAssignClick = (reseller: Reseller) => {
    setSelectedReseller(reseller);
    setShowAssignModal(true);
  };

  const handleViewClick = (reseller: Reseller) => {
    setSelectedReseller(reseller);
    setShowViewModal(true);
  };

  const handleDelete = async (reseller: Reseller) => {
    if (!confirm(`Sei sicuro di voler eliminare il reseller "${reseller.name || reseller.email}"?`)) {
      return;
    }

    try {
      await resellersApi.delete(reseller.user_id);
      onRefresh();
    } catch (err: any) {
      alert('Errore durante l\'eliminazione: ' + err.message);
    }
  };

  // Filter and search logic
  const filteredResellers = useMemo(() => {
    let filtered = [...resellers];

    // Apply search filter
    if (searchTerm.trim()) {
      const searchLower = searchTerm.toLowerCase();
      filtered = filtered.filter(
        (reseller) =>
          reseller.name?.toLowerCase().includes(searchLower) ||
          reseller.email.toLowerCase().includes(searchLower)
      );
    }

    // Apply tenant count filter
    if (filterTenantsCount !== 'all') {
      switch (filterTenantsCount) {
        case '0':
          filtered = filtered.filter((r) => (r.assigned_tenants_count || 0) === 0);
          break;
        case '1-5':
          filtered = filtered.filter((r) => {
            const c = r.assigned_tenants_count || 0;
            return c >= 1 && c <= 5;
          });
          break;
        case '6-10':
          filtered = filtered.filter((r) => {
            const c = r.assigned_tenants_count || 0;
            return c >= 6 && c <= 10;
          });
          break;
        case '10+':
          filtered = filtered.filter((r) => (r.assigned_tenants_count || 0) > 10);
          break;
      }
    }

    // Apply date range filter
    if (filterDateRange !== 'all' && filterDateRange !== 'none') {
      const now = new Date();
      filtered = filtered.filter((reseller) => {
        if (!reseller.created_at) return false;
        
        const createdDate = new Date(reseller.created_at);
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
      // Filter out resellers without created_at
      filtered = filtered.filter((reseller) => !reseller.created_at);
    }

    return filtered;
  }, [resellers, searchTerm, filterTenantsCount, filterDateRange]);

  return (
    <>
      <div className="card">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-2xl font-semibold text-gray-800">Gestione Reseller</h3>
          <button
            onClick={() => setShowCreateModal(true)}
            className="btn btn-primary"
          >
            + Crea Nuovo Reseller
          </button>
        </div>

        <SearchAndFilter
          searchPlaceholder="Cerca per nome o email..."
          searchValue={searchTerm}
          onSearchChange={setSearchTerm}
          showFilters={showFilters}
          onToggleFilters={() => setShowFilters(!showFilters)}
          filters={[
            {
              label: 'Tenant Assegnati',
              key: 'tenantsCount',
              value: filterTenantsCount,
              onChange: setFilterTenantsCount,
              options: [
                { label: 'Tutti', value: 'all' },
                { label: 'Nessuno (0)', value: '0' },
                { label: '1-5 tenant', value: '1-5' },
                { label: '6-10 tenant', value: '6-10' },
                { label: 'Più di 10 tenant', value: '10+' },
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
              <tr className="bg-gray-50">
                <th className="px-4 py-3 text-left font-semibold text-gray-800 border-b">Nome</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-800 border-b">Email</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-800 border-b">Tenant Assegnati</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-800 border-b">Azioni</th>
              </tr>
            </thead>
            <tbody>
              {filteredResellers.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-gray-500">
                    {resellers.length === 0
                      ? 'Nessun reseller trovato'
                      : 'Nessun reseller corrisponde ai filtri selezionati'}
                  </td>
                </tr>
              ) : (
                filteredResellers.map((reseller) => (
                  <tr key={reseller.user_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 border-b">{reseller.name || 'N/A'}</td>
                    <td className="px-4 py-3 border-b">{reseller.email}</td>
                    <td className="px-4 py-3 border-b">
                      <span className="badge bg-blue-100 text-blue-800">
                        {reseller.assigned_tenants_count || 0} tenant
                      </span>
                    </td>
                    <td className="px-4 py-3 border-b">
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleViewClick(reseller)}
                          className="btn btn-small bg-blue-500 hover:bg-blue-600 text-white"
                        >
                          Vedi Tenant
                        </button>
                        <button
                          onClick={() => handleAssignClick(reseller)}
                          className="btn btn-small bg-green-500 hover:bg-green-600 text-white"
                        >
                          Assegna Tenant
                        </button>
                        <button
                          onClick={() => handleDelete(reseller)}
                          className="btn btn-small btn-danger"
                        >
                          Elimina
                        </button>
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
        <CreateResellerModal
          onClose={() => setShowCreateModal(false)}
          onSuccess={handleCreateSuccess}
        />
      )}

      {showAssignModal && selectedReseller && (
        <AssignTenantModal
          reseller={selectedReseller}
          tenants={tenants}
          onClose={() => {
            setShowAssignModal(false);
            setSelectedReseller(null);
          }}
          onSuccess={() => {
            setShowAssignModal(false);
            setSelectedReseller(null);
            onRefresh();
          }}
        />
      )}

      {showViewModal && selectedReseller && (
        <ViewResellerTenantsModal
          reseller={selectedReseller}
          onClose={() => {
            setShowViewModal(false);
            setSelectedReseller(null);
          }}
          onRefresh={onRefresh}
        />
      )}
    </>
  );
}

