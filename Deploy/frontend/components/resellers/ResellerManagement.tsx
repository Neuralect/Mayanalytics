'use client';

import { useState, useMemo, useEffect } from 'react';
import { ResellerOrganization, Tenant, Reseller } from '@/types';
import { resellerOrganizationsApi, resellersApi } from '@/lib/api';
import CreateResellerOrganizationModal from './CreateResellerOrganizationModal';
import CreateResellerModal from './CreateResellerModal';
import ResellerOrganizationUsersModal from './ResellerOrganizationUsersModal';
import AssignTenantToOrganizationModal from './AssignTenantToOrganizationModal';
import SearchAndFilter from '../common/SearchAndFilter';

interface Props {
  resellers: Reseller[];
  tenants: Tenant[];
  onRefresh: () => void;
}

export default function ResellerManagement({ resellers, tenants, onRefresh }: Props) {
  const [organizations, setOrganizations] = useState<ResellerOrganization[]>([]);
  const [showCreateOrgModal, setShowCreateOrgModal] = useState(false);
  const [showCreateUserModal, setShowCreateUserModal] = useState(false);
  const [showUsersModal, setShowUsersModal] = useState(false);
  const [showAssignTenantModal, setShowAssignTenantModal] = useState(false);
  const [selectedOrganization, setSelectedOrganization] = useState<ResellerOrganization | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [filterUsersCount, setFilterUsersCount] = useState('all');
  const [filterTenantsCount, setFilterTenantsCount] = useState('all');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadOrganizations();
  }, []);

  const loadOrganizations = async () => {
    try {
      setLoading(true);
      const response = await resellerOrganizationsApi.list();
      if (response.organizations) {
        setOrganizations(response.organizations);
      }
    } catch (error) {
      console.error('Error loading organizations:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateOrgSuccess = () => {
    setShowCreateOrgModal(false);
    loadOrganizations();
    onRefresh();
  };

  const handleCreateUserSuccess = () => {
    setShowCreateUserModal(false);
    loadOrganizations();
    onRefresh();
  };

  const handleUsersClick = (org: ResellerOrganization) => {
    setSelectedOrganization(org);
    setShowUsersModal(true);
  };

  const handleAssignTenantClick = (org: ResellerOrganization) => {
    setSelectedOrganization(org);
    setShowAssignTenantModal(true);
  };

  const handleDelete = async (org: ResellerOrganization) => {
    if (!confirm(`Sei sicuro di voler eliminare il ruolo reseller "${org.name}"?`)) {
      return;
    }

    try {
      await resellerOrganizationsApi.delete(org.org_id);
      loadOrganizations();
      onRefresh();
    } catch (err: any) {
      alert('Errore durante l\'eliminazione: ' + err.message);
    }
  };

  // Filter and search logic
  const filteredOrganizations = useMemo(() => {
    let filtered = [...organizations];

    // Apply search filter
    if (searchTerm.trim()) {
      const searchLower = searchTerm.toLowerCase();
      filtered = filtered.filter(
        (org) =>
          org.name?.toLowerCase().includes(searchLower) ||
          org.description?.toLowerCase().includes(searchLower)
      );
    }

    // Apply users count filter
    if (filterUsersCount !== 'all') {
      switch (filterUsersCount) {
        case '0':
          filtered = filtered.filter((o) => (o.users_count || 0) === 0);
          break;
        case '1-5':
          filtered = filtered.filter((o) => {
            const c = o.users_count || 0;
            return c >= 1 && c <= 5;
          });
          break;
        case '6-10':
          filtered = filtered.filter((o) => {
            const c = o.users_count || 0;
            return c >= 6 && c <= 10;
          });
          break;
        case '10+':
          filtered = filtered.filter((o) => (o.users_count || 0) > 10);
          break;
      }
    }

    // Apply tenants count filter
    if (filterTenantsCount !== 'all') {
      switch (filterTenantsCount) {
        case '0':
          filtered = filtered.filter((o) => (o.tenants_count || 0) === 0);
          break;
        case '1-5':
          filtered = filtered.filter((o) => {
            const c = o.tenants_count || 0;
            return c >= 1 && c <= 5;
          });
          break;
        case '6-10':
          filtered = filtered.filter((o) => {
            const c = o.tenants_count || 0;
            return c >= 6 && c <= 10;
          });
          break;
        case '10+':
          filtered = filtered.filter((o) => (o.tenants_count || 0) > 10);
          break;
      }
    }

    return filtered;
  }, [organizations, searchTerm, filterUsersCount, filterTenantsCount]);

  if (loading) {
    return (
      <div className="flex justify-center items-center min-h-[400px]">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600 mb-4"></div>
          <p className="text-gray-600">Caricamento...</p>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="card">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-2xl font-semibold text-gray-800">Ruolo Reseller</h3>
          <div className="flex gap-2">
            <button
              onClick={() => setShowCreateOrgModal(true)}
              className="btn btn-primary"
            >
              + Crea Ruolo Reseller
            </button>
            <button
              onClick={() => setShowCreateUserModal(true)}
              className="btn btn-secondary"
            >
              + Crea Utente Reseller
            </button>
          </div>
        </div>

        <SearchAndFilter
          searchPlaceholder="Cerca per nome o descrizione..."
          searchValue={searchTerm}
          onSearchChange={setSearchTerm}
          showFilters={showFilters}
          onToggleFilters={() => setShowFilters(!showFilters)}
          filters={[
            {
              label: 'Utenti Reseller',
              key: 'usersCount',
              value: filterUsersCount,
              onChange: setFilterUsersCount,
              options: [
                { label: 'Tutti', value: 'all' },
                { label: 'Nessuno (0)', value: '0' },
                { label: '1-5 utenti', value: '1-5' },
                { label: '6-10 utenti', value: '6-10' },
                { label: 'Più di 10 utenti', value: '10+' },
              ],
            },
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
          ]}
        />

        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-gray-50">
                <th className="px-4 py-3 text-left font-semibold text-gray-800 border-b">Nome</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-800 border-b">Descrizione</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-800 border-b">Utenti Reseller</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-800 border-b">Tenant Assegnati</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-800 border-b">Azioni</th>
              </tr>
            </thead>
            <tbody>
              {filteredOrganizations.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-gray-500">
                    {organizations.length === 0
                      ? 'Nessun ruolo reseller trovato'
                      : 'Nessun ruolo reseller corrisponde ai filtri selezionati'}
                  </td>
                </tr>
              ) : (
                filteredOrganizations.map((org) => (
                  <tr key={org.org_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 border-b font-medium">{org.name}</td>
                    <td className="px-4 py-3 border-b text-gray-600">
                      {org.description || 'Nessuna descrizione'}
                    </td>
                    <td className="px-4 py-3 border-b">
                      <span className="badge bg-blue-100 text-blue-800">
                        {org.users_count || 0} utenti
                      </span>
                    </td>
                    <td className="px-4 py-3 border-b">
                      <span className="badge bg-green-100 text-green-800">
                        {org.tenants_count || 0} tenant
                      </span>
                    </td>
                    <td className="px-4 py-3 border-b">
                      <div className="flex gap-2 flex-wrap">
                        <button
                          onClick={() => handleUsersClick(org)}
                          className="btn btn-small bg-blue-500 hover:bg-blue-600 text-white"
                        >
                          Gestisci Utenti
                        </button>
                        <button
                          onClick={() => handleAssignTenantClick(org)}
                          className="btn btn-small bg-green-500 hover:bg-green-600 text-white"
                        >
                          Assegna Tenant
                        </button>
                        <button
                          onClick={() => handleDelete(org)}
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

      {showCreateOrgModal && (
        <CreateResellerOrganizationModal
          onClose={() => setShowCreateOrgModal(false)}
          onSuccess={handleCreateOrgSuccess}
        />
      )}

      {showCreateUserModal && (
        <CreateResellerModal
          onClose={() => setShowCreateUserModal(false)}
          onSuccess={handleCreateUserSuccess}
        />
      )}

      {showUsersModal && selectedOrganization && (
        <ResellerOrganizationUsersModal
          organization={selectedOrganization}
          onClose={() => {
            setShowUsersModal(false);
            setSelectedOrganization(null);
          }}
          onRefresh={() => {
            loadOrganizations();
            onRefresh();
          }}
        />
      )}

      {showAssignTenantModal && selectedOrganization && (
        <AssignTenantToOrganizationModal
          organization={selectedOrganization}
          tenants={tenants}
          onClose={() => {
            setShowAssignTenantModal(false);
            setSelectedOrganization(null);
          }}
          onSuccess={() => {
            setShowAssignTenantModal(false);
            setSelectedOrganization(null);
            loadOrganizations();
            onRefresh();
          }}
        />
      )}
    </>
  );
}
