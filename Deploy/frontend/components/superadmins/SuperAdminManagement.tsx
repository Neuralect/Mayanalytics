'use client';

import { useState, useMemo } from 'react';
import { SuperAdmin } from '@/types';
import { superadminsApi } from '@/lib/api';
import CreateSuperAdminModal from './CreateSuperAdminModal';
import SearchAndFilter from '../common/SearchAndFilter';

interface Props {
  superadmins: SuperAdmin[];
  onRefresh: () => void;
}

export default function SuperAdminManagement({ superadmins, onRefresh }: Props) {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [filterDateRange, setFilterDateRange] = useState('all');

  const handleCreateSuccess = () => {
    setShowCreateModal(false);
    onRefresh();
  };

  // Filter and search logic
  const filteredSuperAdmins = useMemo(() => {
    let filtered = [...superadmins];

    // Apply search filter
    if (searchTerm.trim()) {
      const searchLower = searchTerm.toLowerCase();
      filtered = filtered.filter(
        (superadmin) =>
          superadmin.name?.toLowerCase().includes(searchLower) ||
          superadmin.email.toLowerCase().includes(searchLower)
      );
    }

    // Apply date range filter
    if (filterDateRange !== 'all' && filterDateRange !== 'none') {
      const now = new Date();
      filtered = filtered.filter((superadmin) => {
        if (!superadmin.created_at) return false;
        
        const createdDate = new Date(superadmin.created_at);
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
      // Filter out superadmins without created_at
      filtered = filtered.filter((superadmin) => !superadmin.created_at);
    }

    return filtered;
  }, [superadmins, searchTerm, filterDateRange]);

  return (
    <>
      <div className="card">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-2xl font-semibold text-gray-800">Gestione SuperAdmin</h3>
          <button
            onClick={() => setShowCreateModal(true)}
            className="btn btn-primary"
          >
            + Crea Nuovo SuperAdmin
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
                <th className="px-4 py-3 text-left font-semibold text-gray-800 border-b">Data Creazione</th>
              </tr>
            </thead>
            <tbody>
              {filteredSuperAdmins.length === 0 ? (
                <tr>
                  <td colSpan={3} className="px-4 py-8 text-center text-gray-500">
                    {superadmins.length === 0
                      ? 'Nessun superadmin trovato'
                      : 'Nessun superadmin corrisponde ai filtri selezionati'}
                  </td>
                </tr>
              ) : (
                filteredSuperAdmins.map((superadmin) => (
                  <tr key={superadmin.user_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 border-b">{superadmin.name || 'N/A'}</td>
                    <td className="px-4 py-3 border-b">{superadmin.email}</td>
                    <td className="px-4 py-3 border-b">
                      {(() => {
                        if (!superadmin.created_at) return 'N/A';
                        
                        // Try to parse the date - handle different formats
                        let date: Date;
                        const dateValue = superadmin.created_at;
                        
                        // If it's a number (timestamp), convert it
                        if (typeof dateValue === 'number') {
                          date = new Date(dateValue);
                        } else if (typeof dateValue === 'string') {
                          // Try parsing as ISO string
                          date = new Date(dateValue);
                          // If that fails, try as timestamp string
                          if (isNaN(date.getTime()) && !isNaN(Number(dateValue))) {
                            date = new Date(Number(dateValue));
                          }
                        } else {
                          return 'N/A';
                        }
                        
                        // Check if date is valid
                        if (isNaN(date.getTime())) {
                          console.warn('Invalid date for superadmin:', superadmin.email, 'date value:', dateValue);
                          return 'N/A';
                        }
                        
                        return date.toLocaleDateString('it-IT', {
                          year: 'numeric',
                          month: 'long',
                          day: 'numeric',
                        });
                      })()}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {showCreateModal && (
        <CreateSuperAdminModal
          onClose={() => setShowCreateModal(false)}
          onSuccess={handleCreateSuccess}
        />
      )}
    </>
  );
}

