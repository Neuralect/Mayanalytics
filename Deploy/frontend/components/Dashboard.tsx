'use client';

import { useAuth } from '@/contexts/AuthContext';
import SuperAdminDashboard from './dashboards/SuperAdminDashboard';
import AdminDashboard from './dashboards/AdminDashboard';
import DashboardHeader from './DashboardHeader';

export default function Dashboard() {
  const { user } = useAuth();

  if (!user) return null;

  // End-users (role='User') don't have access - they only receive emails
  if (user.role === 'User') {
    return (
      <div className="min-h-screen p-5 flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl font-semibold text-gray-800 mb-4">
            Accesso non disponibile
          </h2>
          <p className="text-gray-600">
            Gli utenti finali ricevono solo report automatici via email.
            <br />
            Non è necessario accedere al sistema.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard-content min-h-screen p-5">
      <div className="max-w-7xl mx-auto">
        <DashboardHeader />
        
        {user.role === 'SuperAdmin' || user.role === 'Reseller' ? (
          <SuperAdminDashboard />
        ) : user.role === 'Admin' ? (
          <AdminDashboard />
        ) : null}
      </div>
    </div>
  );
}

