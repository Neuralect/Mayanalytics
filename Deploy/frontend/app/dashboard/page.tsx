'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { tenantsApi, superadminsApi } from '@/lib/api';
import { Tenant, SuperAdmin } from '@/types';
import SuperAdminManagement from '@/components/superadmins/SuperAdminManagement';
import AdminDashboard from '@/components/dashboards/AdminDashboard';

export default function DashboardPage() {
  const { user, selectedTenantId, setSelectedTenantId } = useAuth();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [superadmins, setSuperadmins] = useState<SuperAdmin[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (user?.role === 'SuperAdmin' || user?.role === 'Reseller') {
      // Only load data if no tenant is selected (global view)
      if (!selectedTenantId) {
        loadData();
      } else {
        // If tenant is selected, we're in tenant context - don't load superadmin data
        setLoading(false);
      }
    } else if (user?.role === 'Admin') {
      setLoading(false);
    }
  }, [user, selectedTenantId]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [tenantsRes, superadminsRes] = await Promise.all([
        tenantsApi.list(),
        user?.role === 'SuperAdmin' ? superadminsApi.list() : Promise.resolve({ superadmins: [] }),
      ]);
      
      if (tenantsRes.tenants) setTenants(tenantsRes.tenants);
      if (superadminsRes.superadmins) setSuperadmins(superadminsRes.superadmins);
    } catch (error) {
      console.error('Error loading data:', error);
    } finally {
      setLoading(false);
    }
  };

  // If a tenant is selected, show AdminDashboard in tenant context
  if (selectedTenantId && (user?.role === 'SuperAdmin' || user?.role === 'Reseller')) {
    return (
      <div className="dashboard-content min-h-screen">
        <div>
          <AdminDashboard tenantId={selectedTenantId} />
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="dashboard-content min-h-screen flex justify-center items-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-[#286291] mb-4"></div>
          <p className="text-gray-600">Caricamento...</p>
        </div>
      </div>
    );
  }

  // For SuperAdmin: show SuperAdminManagement
  // For Admin: show AdminDashboard
  // For Reseller: show nothing (they should use tenants page)
  return (
    <div className="dashboard-content min-h-screen">
      <div>
        {user?.role === 'SuperAdmin' && (
          <SuperAdminManagement 
            superadmins={superadmins}
            onRefresh={loadData}
          />
        )}
        {user?.role === 'Admin' && (
          <AdminDashboard />
        )}
      </div>
    </div>
  );
}

