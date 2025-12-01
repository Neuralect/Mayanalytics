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
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-2xl font-semibold text-gray-800">Gestione Utenti</h3>
          <button
            onClick={() => setShowCreateModal(true)}
            className="btn btn-primary"
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
              <tr className="bg-gray-50">
                <th className="px-4 py-3 text-left font-semibold text-gray-800 border-b">Nome</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-800 border-b">Email</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-800 border-b">Connettori</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-800 border-b">Azioni</th>
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
                    <tr key={user.user_id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 border-b">{user.name || 'N/A'}</td>
                      <td className="px-4 py-3 border-b">{user.report_email || user.email}</td>
                      <td className="px-4 py-3 border-b">
                        <span className="badge bg-blue-100 text-blue-800">
                          {connectors.length} connettore{connectors.length !== 1 ? 'i' : ''}
                          {enabledConnectors > 0 && ` (${enabledConnectors} attivo${enabledConnectors !== 1 ? 'i' : ''})`}
                        </span>
                      </td>
                      <td className="px-4 py-3 border-b">
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleEdit(user)}
                            className="btn btn-small bg-blue-500 hover:bg-blue-600 text-white"
                          >
                            Modifica
                          </button>
                          <button
                            onClick={() => handleDelete(user.user_id)}
                            className="btn btn-small btn-danger"
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

