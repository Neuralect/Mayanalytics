'use client';

import { useState, useMemo } from 'react';
import { User } from '@/types';
import { usersApi } from '@/lib/api';
import { formatReportSchedule } from '@/lib/utils';
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
  const [showFilters, setShowFilters] = useState(false);
  const [filterReportEnabled, setFilterReportEnabled] = useState('all');
  const [filterRole, setFilterRole] = useState('all');

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
          user.email.toLowerCase().includes(searchLower)
      );
    }

    // Apply report enabled filter
    if (filterReportEnabled !== 'all') {
      filtered = filtered.filter((user) => {
        const enabled = user.report_enabled || false;
        return filterReportEnabled === 'yes' ? enabled : !enabled;
      });
    }

    // Apply role filter
    if (filterRole !== 'all') {
      filtered = filtered.filter((user) => user.role === filterRole);
    }

    return filtered;
  }, [users, searchTerm, filterReportEnabled, filterRole]);

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
          showFilters={showFilters}
          onToggleFilters={() => setShowFilters(!showFilters)}
          filters={[
            {
              label: 'Report Attivi',
              key: 'reportEnabled',
              value: filterReportEnabled,
              onChange: setFilterReportEnabled,
              options: [
                { label: 'Tutti', value: 'all' },
                { label: 'Sì', value: 'yes' },
                { label: 'No', value: 'no' },
              ],
            },
            {
              label: 'Ruolo',
              key: 'role',
              value: filterRole,
              onChange: setFilterRole,
              options: [
                { label: 'Tutti', value: 'all' },
                { label: 'Admin', value: 'Admin' },
                { label: 'User', value: 'User' },
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
                <th className="px-4 py-3 text-left font-semibold text-gray-800 border-b">Report Attivi</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-800 border-b">Periodicità</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-800 border-b">Azioni</th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-gray-500">
                    {users.length === 0
                      ? 'Nessun utente trovato'
                      : 'Nessun utente corrisponde ai filtri selezionati'}
                  </td>
                </tr>
              ) : (
                filteredUsers.map((user) => (
                  <tr key={user.user_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 border-b">{user.name || 'N/A'}</td>
                    <td className="px-4 py-3 border-b">{user.email}</td>
                    <td className="px-4 py-3 border-b">
                      <span className={`badge ${user.report_enabled ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'}`}>
                        {user.report_enabled ? 'Sì' : 'No'}
                      </span>
                    </td>
                    <td className="px-4 py-3 border-b">{formatReportSchedule(user.report_schedule ?? null)}</td>
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
                ))
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

