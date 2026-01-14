'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { usersApi } from '@/lib/api';
import { User } from '@/types';
import UserManagement from '../users/UserManagement';

interface AdminDashboardProps {
  tenantId?: string;
}

export default function AdminDashboard({ tenantId: propTenantId }: AdminDashboardProps = {}) {
  const { user } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);

  // Use prop tenantId if provided (SuperAdmin/Reseller context), otherwise use user's tenant_id
  const tenantId = propTenantId || user?.tenant_id;

  useEffect(() => {
    if (tenantId) {
      loadUsers();
    }
  }, [tenantId]);

  const loadUsers = async () => {
    if (!tenantId) return;
    
    try {
      setLoading(true);
      const response = await usersApi.list(tenantId);
      setUsers(response.users || []);
    } catch (error) {
      console.error('Error loading users:', error);
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

  return (
    <div>
      <UserManagement 
        users={users}
        tenantId={tenantId || ''}
        onRefresh={loadUsers}
      />
    </div>
  );
}
