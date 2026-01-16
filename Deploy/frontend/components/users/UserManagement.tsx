'use client';

import { useState, useMemo } from 'react';
import { User } from '@/types';
import { usersApi } from '@/lib/api';
import CreateUserModal from './CreateUserModal';
import EditUserModal from './EditUserModal';
import SearchAndFilter from '../common/SearchAndFilter';

interface Props {
  users: User[];
  tenantId: string;
  onRefresh: () => void;
}

export default function UserManagement({ users, tenantId, onRefresh }: Props) {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [searchTerm, setSearchTerm] = useState('');

  const handleEdit = (user: User) => {
    setSelectedUser(user);
    setShowEditModal(true);
  };

  const handleDelete = async (userId: string) => {
    if (!confirm('Sei sicuro di voler eliminare questo utente?')) {
      return;
    }

    try {
      await usersApi.delete(userId);
      onRefresh();
    } catch (err: any) {
      alert('Errore durante l\'eliminazione: ' + err.message);
    }
  };

  // Filter and search logic
  const filteredUsers = useMemo(() => {
    let filtered = [...users];

    // Apply search filter
    if (searchTerm.trim()) {
      const searchLower = searchTerm.toLowerCase();
      filtered = filtered.filter(
        (user) =>
          user.name?.toLowerCase().includes(searchLower) ||
          user.email.toLowerCase().includes(searchLower) ||
          (user.report_email && user.report_email.toLowerCase().includes(searchLower))
      );
    }

    return filtered;
  }, [users, searchTerm]);

  return (
    <>
      <div className="card">
        <div className="content-card">
          <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3 mb-4">
            <h3 className="text-xl sm:text-2xl font-semibold text-gray-800">Gestione Utenti</h3>
          <button
            onClick={() => setShowCreateModal(true)}
            className="btn bg-[#286291] hover:bg-[#113357] text-white w-full sm:w-auto text-sm sm:text-base whitespace-nowrap"
          >
            + Crea Nuovo Utente
          </button>
          </div>

          <SearchAndFilter
            searchPlaceholder="Cerca per nome o email..."
            searchValue={searchTerm}
            onSearchChange={setSearchTerm}
            showFilters={false}
            onToggleFilters={() => {}}
            filters={[]}
          />

          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr>
                  <th className="px-4 py-3 text-left font-semibold text-gray-800">Nome</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-800">Email</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-800">Connettori</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-800">Azioni</th>
                </tr>
              </thead>
              <tbody>
                {filteredUsers.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-gray-500">
                      {users.length === 0
                        ? 'Nessun utente trovato'
                        : 'Nessun utente corrisponde ai filtri selezionati'}
                    </td>
                  </tr>
                ) : (
                  filteredUsers.map((user) => {
                    const connectors = (user as any).connectors || [];
                    const enabledConnectors = connectors.filter((c: any) => c.report_enabled !== false).length;
                    
                    return (
                      <tr key={user.user_id}>
                        <td className="px-4 py-3 text-gray-800">{user.name || 'N/A'}</td>
                        <td className="px-4 py-3 text-gray-800">{user.report_email || user.email}</td>
                        <td className="px-4 py-3">
                          <span className="badge bg-[#eeeeee] text-[#286291]">
                            {connectors.length} connettore{connectors.length !== 1 ? 'i' : ''}
                            {enabledConnectors > 0 && ` (${enabledConnectors} attivo${enabledConnectors !== 1 ? 'i' : ''})`}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex gap-2">
                            <button
                              onClick={() => handleEdit(user)}
                              className="btn btn-small bg-[#286291] hover:bg-[#113357] text-white"
                            >
                              Modifica
                            </button>
                          <button
                            onClick={() => handleDelete(user.user_id)}
                            className="btn btn-small bg-[#286291] hover:bg-[#113357] text-white"
                          >
                            Elimina
                          </button>
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

      {showCreateModal && (
        <CreateUserModal
          tenantId={tenantId}
          onClose={() => setShowCreateModal(false)}
          onSuccess={() => {
            setShowCreateModal(false);
            onRefresh();
          }}
        />
      )}

      {showEditModal && selectedUser && (
        <EditUserModal
          user={selectedUser}
          onClose={() => {
            setShowEditModal(false);
            setSelectedUser(null);
          }}
          onSuccess={() => {
            setShowEditModal(false);
            setSelectedUser(null);
            onRefresh();
          }}
        />
      )}
    </>
  );
}

