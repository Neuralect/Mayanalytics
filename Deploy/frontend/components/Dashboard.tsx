'use client';

import { useAuth } from '@/contexts/AuthContext';
import SuperAdminDashboard from './dashboards/SuperAdminDashboard';
import AdminDashboard from './dashboards/AdminDashboard';
import UserDashboard from './dashboards/UserDashboard';
import DashboardHeader from './DashboardHeader';

export default function Dashboard() {
  const { user } = useAuth();

  if (!user) return null;

  return (
    <div className="min-h-screen p-5">
      <div className="max-w-7xl mx-auto">
        <DashboardHeader />
        
        {user.role === 'SuperAdmin' || user.role === 'Reseller' ? (
          <SuperAdminDashboard />
        ) : user.role === 'Admin' ? (
          <AdminDashboard />
        ) : (
          <UserDashboard />
        )}
      </div>
    </div>
  );
}

