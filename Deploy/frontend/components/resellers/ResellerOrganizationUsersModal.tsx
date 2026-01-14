'use client';

import { useState, useEffect } from 'react';
import { resellerOrganizationsApi, resellersApi } from '@/lib/api';
import { ResellerOrganization, Reseller } from '@/types';

interface Props {
  organization: ResellerOrganization;
  onClose: () => void;
  onRefresh: () => void;
}

export default function ResellerOrganizationUsersModal({ organization, onClose, onRefresh }: Props) {
  const [users, setUsers] = useState<Reseller[]>([]);
  const [allResellers, setAllResellers] = useState<Reseller[]>([]);
  const [unassociatedResellers, setUnassociatedResellers] = useState<Reseller[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showAddUser, setShowAddUser] = useState(false);
  const [showUnassociated, setShowUnassociated] = useState(false);
  const [selectedUserId, setSelectedUserId] = useState('');

  useEffect(() => {
    loadData();
  }, [organization]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [resellersRes, orgsRes] = await Promise.all([
        resellersApi.list(),
        resellerOrganizationsApi.list(),
      ]);
      
      if (resellersRes.resellers) {
        setAllResellers(resellersRes.resellers);
        
        // Find the current organization in the updated list
        const currentOrg = orgsRes.organizations?.find((org: ResellerOrganization) => 
          org.org_id === organization.org_id
        );
        
        // Filter users that belong to this organization
        const orgUserIds = currentOrg?.users || organization.users || [];
        const orgUsers = resellersRes.resellers.filter((r: Reseller) => 
          orgUserIds.includes(r.user_id)
        );
        setUsers(orgUsers);
        
        // Find resellers not associated with any organization
        if (orgsRes.organizations) {
          const allAssociatedUserIds = new Set<string>();
          orgsRes.organizations.forEach((org: ResellerOrganization) => {
            (org.users || []).forEach((userId: string) => {
              allAssociatedUserIds.add(userId);
            });
          });
          
          const unassociated = resellersRes.resellers.filter((r: Reseller) => 
            !allAssociatedUserIds.has(r.user_id)
          );
          setUnassociatedResellers(unassociated);
        } else {
          // If no organizations, all resellers are unassociated
          setUnassociatedResellers(resellersRes.resellers);
        }
      }
    } catch (err: any) {
      setError(err.message || 'Errore nel caricamento degli utenti');
    } finally {
      setLoading(false);
    }
  };

  const handleAddUser = async () => {
    if (!selectedUserId) {
      setError('Seleziona un utente reseller');
      return;
    }

    try {
      setError('');
      await resellerOrganizationsApi.addUser(organization.org_id, { user_id: selectedUserId });
      onRefresh();
      setShowAddUser(false);
      setSelectedUserId('');
      loadData();
    } catch (err: any) {
      setError(err.message || 'Errore nell\'aggiunta dell\'utente');
    }
  };

  const handleRemoveUser = async (userId: string) => {
    if (!confirm('Sei sicuro di voler rimuovere questo utente dall\'organizzazione? L\'utente diventerà indipendente.')) {
      return;
    }

    try {
      setError('');
      await resellerOrganizationsApi.removeUser(organization.org_id, userId);
      onRefresh();
      loadData();
    } catch (err: any) {
      setError(err.message || 'Errore nella rimozione dell\'utente');
    }
  };

  // Get available resellers (not already in organization)
  const availableResellers = allResellers.filter((r: Reseller) => 
    !(organization.users || []).includes(r.user_id)
  );

  return (
    <div className="fixed inset-0 modal-backdrop flex items-center justify-center z-50 p-4">
      <div className="card max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-2xl font-semibold text-gray-800">
            Utenti Reseller - {organization.name}
          </h3>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 text-2xl"
          >
            ×
          </button>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4">
            {error}
          </div>
        )}

        <div className="mb-4">
          <button
            onClick={() => setShowAddUser(!showAddUser)}
            className="btn bg-[#286291] hover:bg-[#113357] text-white"
            disabled={availableResellers.length === 0}
          >
            + Aggiungi Utente Reseller
          </button>
          {availableResellers.length === 0 && (
            <p className="text-sm text-gray-500 mt-2">
              Tutti gli utenti reseller sono già associati a questa organizzazione
            </p>
          )}
        </div>

        {showAddUser && (
          <div className="bg-gray-50 p-4 rounded-lg mb-4">
            <label className="block text-gray-700 font-medium mb-2">
              Seleziona Utente Reseller
            </label>
            <select
              value={selectedUserId}
              onChange={(e) => setSelectedUserId(e.target.value)}
              className="input mb-2"
            >
              <option value="">-- Seleziona un utente --</option>
              {availableResellers.map((reseller: Reseller) => (
                <option key={reseller.user_id} value={reseller.user_id}>
                  {reseller.name || reseller.email} ({reseller.email})
                </option>
              ))}
            </select>
            <div className="flex gap-2">
              <button
                onClick={handleAddUser}
                disabled={!selectedUserId}
                className="btn bg-[#286291] hover:bg-[#113357] text-white"
              >
                Aggiungi
              </button>
              <button
                onClick={() => {
                  setShowAddUser(false);
                  setSelectedUserId('');
                }}
                className="btn btn-secondary"
              >
                Annulla
              </button>
            </div>
          </div>
        )}

        {loading ? (
          <div className="text-center py-8">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-[#286291]"></div>
            <p className="text-gray-600 mt-2">Caricamento...</p>
          </div>
        ) : users.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            Nessun utente reseller associato a questa organizzazione
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr>
                  <th className="px-4 py-3 text-left font-semibold text-white border-b">Nome</th>
                  <th className="px-4 py-3 text-left font-semibold text-white border-b">Email</th>
                  <th className="px-4 py-3 text-left font-semibold text-white border-b">Azioni</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user: Reseller) => (
                  <tr key={user.user_id}>
                    <td className="px-4 py-3 border-b">{user.name || 'N/A'}</td>
                    <td className="px-4 py-3 border-b">{user.email}</td>
                    <td className="px-4 py-3 border-b">
                      <button
                        onClick={() => handleRemoveUser(user.user_id)}
                        className="btn btn-small btn-danger"
                      >
                        Rimuovi
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Unassociated Resellers Section */}
        <div className="mt-8 pt-8 border-t border-gray-200">
          <div className="flex justify-between items-center mb-4">
            <h4 className="text-lg font-semibold text-gray-800">
              Utenti Reseller Non Associati
            </h4>
            <button
              onClick={() => setShowUnassociated(!showUnassociated)}
              className="btn btn-secondary btn-small"
            >
              {showUnassociated ? 'Nascondi' : 'Mostra'} ({unassociatedResellers.length})
            </button>
          </div>

          {showUnassociated && (
            unassociatedResellers.length === 0 ? (
              <div className="text-center py-4 text-gray-500">
                Tutti gli utenti reseller sono associati a un'organizzazione
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full border-collapse">
                  <thead>
                    <tr>
                      <th className="px-4 py-3 text-left font-semibold text-white border-b">Nome</th>
                      <th className="px-4 py-3 text-left font-semibold text-white border-b">Email</th>
                      <th className="px-4 py-3 text-left font-semibold text-white border-b">Azioni</th>
                    </tr>
                  </thead>
                  <tbody>
                    {unassociatedResellers.map((reseller: Reseller) => (
                      <tr key={reseller.user_id}>
                        <td className="px-4 py-3 border-b">{reseller.name || 'N/A'}</td>
                        <td className="px-4 py-3 border-b">{reseller.email}</td>
                        <td className="px-4 py-3 border-b">
                          <button
                            onClick={async () => {
                              try {
                                setError('');
                                await resellerOrganizationsApi.addUser(organization.org_id, { user_id: reseller.user_id });
                                onRefresh();
                                loadData();
                              } catch (err: any) {
                                setError(err.message || 'Errore nell\'aggiunta dell\'utente');
                              }
                            }}
                            className="btn btn-small bg-[#286291] hover:bg-[#113357] text-white"
                          >
                            Aggiungi a questa org
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          )}
        </div>
      </div>
    </div>
  );
}

