'use client';

import { useState } from 'react';
import { Reseller, Tenant } from '@/types';
import { resellersApi } from '@/lib/api';
import CreateResellerModal from './CreateResellerModal';
import AssignTenantModal from './AssignTenantModal';
import ViewResellerTenantsModal from './ViewResellerTenantsModal';

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
              {resellers.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-gray-500">
                    Nessun reseller trovato
                  </td>
                </tr>
              ) : (
                resellers.map((reseller) => (
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

