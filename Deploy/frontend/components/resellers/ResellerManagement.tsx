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
  resellers?: Reseller[];
  tenants: Tenant[];
  onRefresh: () => void;
}

export default function ResellerManagement({ resellers: propResellers, tenants, onRefresh }: Props) {
  const [organizations, setOrganizations] = useState<ResellerOrganization[]>([]);
  const [resellers, setResellers] = useState<Reseller[]>([]);
  const [showCreateOrgModal, setShowCreateOrgModal] = useState(false);
  const [showCreateUserModal, setShowCreateUserModal] = useState(false);
  const [showUsersModal, setShowUsersModal] = useState(false);
  const [showAssignTenantModal, setShowAssignTenantModal] = useState(false);
  const [showAssociateResellerModal, setShowAssociateResellerModal] = useState(false);
  const [selectedOrganization, setSelectedOrganization] = useState<ResellerOrganization | null>(null);
  const [selectedReseller, setSelectedReseller] = useState<Reseller | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [filterUsersCount, setFilterUsersCount] = useState('all');
  const [filterTenantsCount, setFilterTenantsCount] = useState('all');
  const [loading, setLoading] = useState(true);
  const [resellerSearchTerm, setResellerSearchTerm] = useState('');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [orgsRes, resellersRes] = await Promise.all([
        resellerOrganizationsApi.list(),
        resellersApi.list(),
      ]);
      
      if (orgsRes.organizations) {
        setOrganizations(orgsRes.organizations);
      }
      
      if (resellersRes.resellers) {
        setResellers(resellersRes.resellers);
      } else if (propResellers) {
        // Fallback to prop if API doesn't return data
        setResellers(propResellers);
      }
    } catch (error) {
      console.error('Error loading data:', error);
      // Fallback to prop if API fails
      if (propResellers) {
        setResellers(propResellers);
      }
    } finally {
      setLoading(false);
    }
  };

  const loadOrganizations = async () => {
    try {
      const response = await resellerOrganizationsApi.list();
      if (response.organizations) {
        setOrganizations(response.organizations);
      }
    } catch (error) {
      console.error('Error loading organizations:', error);
    }
  };

  // Get all associated user IDs
  const allAssociatedUserIds = useMemo(() => {
    const associatedIds = new Set<string>();
    organizations.forEach((org) => {
      (org.users || []).forEach((userId: string) => {
        associatedIds.add(userId);
      });
    });
    return associatedIds;
  }, [organizations]);

  // Filter resellers
  const filteredResellers = useMemo(() => {
    let filtered = [...resellers];

    // Apply search filter
    if (resellerSearchTerm.trim()) {
      const searchLower = resellerSearchTerm.toLowerCase();
      filtered = filtered.filter(
        (r) =>
          r.name?.toLowerCase().includes(searchLower) ||
          r.email?.toLowerCase().includes(searchLower)
      );
    }

    return filtered;
  }, [resellers, resellerSearchTerm]);

  const handleCreateOrgSuccess = () => {
    setShowCreateOrgModal(false);
    loadData();
    onRefresh();
  };

  const handleCreateUserSuccess = () => {
    setShowCreateUserModal(false);
    loadData();
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

  const handleAssociateReseller = (reseller: Reseller) => {
    setSelectedReseller(reseller);
    setShowAssociateResellerModal(true);
  };

  const handleDeleteReseller = async (resellerId: string, resellerEmail: string) => {
    if (!confirm(`Sei sicuro di voler eliminare l'utente reseller "${resellerEmail}"? Questa azione è irreversibile.`)) {
      return;
    }

    try {
      await resellersApi.delete(resellerId);
      loadData();
      onRefresh();
    } catch (err: any) {
      alert('Errore durante l\'eliminazione: ' + err.message);
    }
  };

  const handleDelete = async (org: ResellerOrganization) => {
    if (!confirm(`Sei sicuro di voler eliminare il ruolo reseller "${org.name}"?`)) {
      return;
    }

    try {
      await resellerOrganizationsApi.delete(org.org_id);
      loadData();
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
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-[#286291] mb-4"></div>
          <p className="text-gray-600">Caricamento...</p>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="card">
        <div className="content-card">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-2xl font-semibold text-gray-800">Ruolo Reseller</h3>
            <div className="flex gap-2">
            <button
              onClick={() => setShowCreateOrgModal(true)}
              className="btn bg-[#286291] hover:bg-[#113357] text-white"
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
                <tr>
                  <th className="px-4 py-3 text-left font-semibold text-gray-800">Nome</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-800">Descrizione</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-800">Utenti Reseller</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-800">Tenant Assegnati</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-800">Azioni</th>
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
                    <tr key={org.org_id}>
                      <td className="px-4 py-3 font-medium text-gray-800">{org.name}</td>
                      <td className="px-4 py-3 text-gray-600">
                        {org.description || 'Nessuna descrizione'}
                      </td>
                      <td className="px-4 py-3">
                        <span className="badge bg-[#eeeeee] text-[#286291]">
                          {org.users_count || 0} utenti
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="badge bg-green-100 text-green-800">
                          {org.tenants_count || 0} tenant
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex gap-2 flex-wrap">
                          <button
                            onClick={() => handleUsersClick(org)}
                            className="btn btn-small bg-[#286291] hover:bg-[#113357] text-white"
                          >
                            Gestisci Utenti
                          </button>
                          <button
                            onClick={() => handleAssignTenantClick(org)}
                            className="btn btn-small bg-[#286291] hover:bg-[#113357] text-white"
                          >
                            Assegna Tenant
                          </button>
                          <button
                            onClick={() => handleDelete(org)}
                            className="btn btn-small bg-[#286291] hover:bg-[#113357] text-white"
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
      </div>

      {/* Reseller Users List */}
      <div className="card mt-6">
        <div className="content-card">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-2xl font-semibold text-gray-800">Utenti Reseller</h3>
          </div>

          <div className="mb-4">
            <div className="relative">
              <input
                type="text"
                placeholder="Cerca per nome o email..."
                value={resellerSearchTerm}
                onChange={(e) => setResellerSearchTerm(e.target.value)}
                className="input w-full"
              />
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr>
                  <th className="px-4 py-3 text-left font-semibold text-gray-800">Nome</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-800">Email</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-800">Stato</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-800">Tenant Assegnati</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-800">Azioni</th>
                </tr>
              </thead>
              <tbody>
                {filteredResellers.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-gray-500">
                      {resellers.length === 0
                        ? 'Nessun utente reseller trovato'
                        : 'Nessun utente reseller corrisponde alla ricerca'}
                    </td>
                  </tr>
                ) : (
                  filteredResellers.map((reseller: Reseller) => {
                    const isIndependent = !allAssociatedUserIds.has(reseller.user_id);
                    const associatedOrg = isIndependent 
                      ? null 
                      : organizations.find((org) => (org.users || []).includes(reseller.user_id));
                    return (
                      <tr key={reseller.user_id}>
                        <td className="px-4 py-3 font-medium text-gray-800">{reseller.name || 'N/A'}</td>
                        <td className="px-4 py-3 text-gray-800">{reseller.email}</td>
                        <td className="px-4 py-3">
                          {isIndependent ? (
                            <span className="badge bg-[#eeeeee] text-[#113357]">
                              Indipendente
                            </span>
                          ) : (
                            <div className="flex items-center gap-2">
                              <span className="badge bg-[#eeeeee] text-[#286291]">
                                Associato
                              </span>
                              {associatedOrg && (
                                <span className="text-sm text-gray-600">
                                  ({associatedOrg.name})
                                </span>
                              )}
                            </div>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <span className="badge bg-green-100 text-green-800">
                            {reseller.assigned_tenants_count || 0} tenant
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex gap-2">
                            {isIndependent && (
                              <>
                                <button
                                  onClick={() => handleAssociateReseller(reseller)}
                                  className="btn btn-small bg-[#286291] hover:bg-[#113357] text-white"
                                >
                                  Associa
                                </button>
                                <button
                                  onClick={() => handleDeleteReseller(reseller.user_id, reseller.email)}
                                  className="btn btn-small bg-[#286291] hover:bg-[#113357] text-white"
                                >
                                  Elimina
                                </button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
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
            loadData();
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
            loadData();
            onRefresh();
          }}
        />
      )}

      {showAssociateResellerModal && selectedReseller && (
        <div className="fixed inset-0 modal-backdrop flex items-center justify-center z-50 p-4">
          <div className="card max-w-md w-full">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-2xl font-semibold text-gray-800">
                Associa Utente Reseller
              </h3>
              <button
                onClick={() => {
                  setShowAssociateResellerModal(false);
                  setSelectedReseller(null);
                }}
                className="text-gray-500 hover:text-gray-700 text-2xl"
              >
                ×
              </button>
            </div>

            <div className="mb-4">
              <p className="text-gray-700 mb-2">
                <strong>Utente:</strong> {selectedReseller.name || selectedReseller.email}
              </p>
              <p className="text-gray-600 text-sm mb-4">
                {selectedReseller.email}
              </p>
            </div>

            <div className="mb-4">
              <label className="block text-gray-700 font-medium mb-2">
                Seleziona Organizzazione Reseller
              </label>
              <select
                id="orgSelect"
                className="input mb-4"
                defaultValue=""
              >
                <option value="">-- Seleziona un'organizzazione --</option>
                {organizations.map((org: ResellerOrganization) => (
                  <option key={org.org_id} value={org.org_id}>
                    {org.name} {org.description ? `- ${org.description}` : ''}
                  </option>
                ))}
              </select>
            </div>

            {organizations.length === 0 && (
              <div className="bg-yellow-50 border border-yellow-200 text-yellow-700 px-4 py-3 rounded-lg mb-4">
                Nessuna organizzazione reseller disponibile. Crea prima un'organizzazione.
              </div>
            )}

            <div className="flex gap-2">
              <button
                onClick={async () => {
                  const select = document.getElementById('orgSelect') as HTMLSelectElement;
                  const orgId = select?.value;
                  
                  if (!orgId) {
                    alert('Seleziona un\'organizzazione');
                    return;
                  }

                  try {
                    await resellerOrganizationsApi.addUser(orgId, { user_id: selectedReseller.user_id });
                    setShowAssociateResellerModal(false);
                    setSelectedReseller(null);
                    loadData();
                    onRefresh();
                  } catch (err: any) {
                    alert('Errore durante l\'associazione: ' + err.message);
                  }
                }}
                disabled={organizations.length === 0}
                className="btn bg-[#286291] hover:bg-[#113357] text-white"
              >
                Associa
              </button>
              <button
                onClick={() => {
                  setShowAssociateResellerModal(false);
                  setSelectedReseller(null);
                }}
                className="btn btn-secondary"
              >
                Annulla
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
