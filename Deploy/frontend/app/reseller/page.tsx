'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { tenantsApi } from '@/lib/api';
import { Tenant } from '@/types';
import ResellerManagement from '@/components/resellers/ResellerManagement';

export default function ResellerPage() {
  const { user } = useAuth();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (user?.role === 'SuperAdmin' || user?.role === 'Reseller') {
      loadData();
    }
  }, [user]);

  const loadData = async () => {
    try {
      setLoading(true);
      const tenantsRes = await tenantsApi.list();
      if (tenantsRes.tenants) setTenants(tenantsRes.tenants);
    } catch (error) {
      console.error('Error loading data:', error);
    } finally {
      setLoading(false);
    }
  };

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

  if (user?.role !== 'SuperAdmin' && user?.role !== 'Reseller') {
    return (
      <div className="flex justify-center items-center min-h-[400px]">
        <div className="text-center">
          <p className="text-gray-600">Accesso non autorizzato</p>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard-content min-h-screen">
      <div>
        <ResellerManagement 
          resellers={[]} 
          tenants={tenants}
          onRefresh={loadData}
        />
      </div>
    </div>
  );
}

