'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { resellersApi, tenantsApi, superadminsApi } from '@/lib/api';
import { Reseller, Tenant, SuperAdmin } from '@/types';
import ResellerManagement from '../resellers/ResellerManagement';
import TenantManagement from '../tenants/TenantManagement';
import SuperAdminManagement from '../superadmins/SuperAdminManagement';
import AdminDashboard from './AdminDashboard';

export default function SuperAdminDashboard() {
  const { user, selectedTenantId } = useAuth();
  const [resellers, setResellers] = useState<Reseller[]>([]);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [superadmins, setSuperadmins] = useState<SuperAdmin[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (user?.role === 'SuperAdmin' || user?.role === 'Reseller') {
      if (!selectedTenantId) {
        loadData();
      }
    }
  }, [user, selectedTenantId]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [resellersRes, tenantsRes, superadminsRes] = await Promise.all([
        user?.role === 'SuperAdmin' ? resellersApi.list() : Promise.resolve({ resellers: [] }),
        tenantsApi.list(),
        user?.role === 'SuperAdmin' ? superadminsApi.list() : Promise.resolve({ superadmins: [] }),
      ]);
      
      if (resellersRes.resellers) setResellers(resellersRes.resellers);
      if (tenantsRes.tenants) setTenants(tenantsRes.tenants);
      if (superadminsRes.superadmins) setSuperadmins(superadminsRes.superadmins);
    } catch (error) {
      console.error('Error loading data:', error);
    } finally {
      setLoading(false);
    }
  };

  // If a tenant is selected, show AdminDashboard in tenant context
  // This check must be AFTER all hooks
  if (selectedTenantId) {
    return <AdminDashboard tenantId={selectedTenantId} />;
  }

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
    <div>
      {user?.role === 'SuperAdmin' && (
        <>
          <SuperAdminManagement 
            superadmins={superadmins}
            onRefresh={loadData}
          />
          <div className="mt-6">
        <ResellerManagement 
          resellers={resellers} 
          tenants={tenants}
          onRefresh={loadData}
        />
          </div>
        </>
      )}
      
      <div className={user?.role === 'SuperAdmin' ? 'mt-6' : ''}>
      <TenantManagement 
        tenants={tenants}
        onRefresh={loadData}
        canCreate={user?.role === 'SuperAdmin' || user?.role === 'Reseller'}
      />
      </div>
    </div>
  );
}
