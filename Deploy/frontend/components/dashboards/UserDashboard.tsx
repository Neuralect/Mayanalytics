'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { reportsApi } from '@/lib/api';
import UserProfile from '../users/UserProfile';

export default function UserDashboard() {
  const { user } = useAuth();
  const [reports, setReports] = useState<any[]>([]);
  const [loadingReports, setLoadingReports] = useState(false);

  useEffect(() => {
    if (user?.user_id) {
      loadReports();
    }
  }, [user]);

  const loadReports = async () => {
    if (!user?.user_id) return;
    
    try {
      setLoadingReports(true);
      const res = await reportsApi.listUser(user.user_id);
      if (res.reports) {
        setReports(res.reports);
      }
    } catch (error) {
      console.error('Error loading reports:', error);
      setReports([]);
    } finally {
      setLoadingReports(false);
    }
  };

  return (
    <div>
      <UserProfile user={user} />
      
      <div className="card">
        <h3 className="text-2xl font-semibold text-gray-800 mb-4">I Miei Report</h3>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr>
                <th className="px-4 py-3 text-left font-semibold text-white border-b">Data</th>
                <th className="px-4 py-3 text-left font-semibold text-white border-b">Stato</th>
                <th className="px-4 py-3 text-left font-semibold text-white border-b">Insights</th>
              </tr>
            </thead>
            <tbody>
              {loadingReports ? (
                <tr>
                  <td colSpan={3} className="px-4 py-8 text-center text-gray-500">
                    Caricamento...
                  </td>
                </tr>
              ) : reports.length === 0 ? (
                <tr>
                  <td colSpan={3} className="px-4 py-8 text-center text-gray-500">
                    Nessun report disponibile
                  </td>
                </tr>
              ) : (
                reports.map((report, idx) => (
                  <tr key={idx}>
                    <td className="px-4 py-3 border-b text-gray-700">
                      {report.report_timestamp ? new Date(report.report_timestamp).toLocaleString('it-IT') : '-'}
                    </td>
                    <td className="px-4 py-3 border-b text-gray-700">
                      {report.status || '-'}
                    </td>
                    <td className="px-4 py-3 border-b text-gray-700">
                      {report.insights || '-'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
