'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { profileApi } from '@/lib/api';
import { User, ReportSchedule } from '@/types';
import { parseReportScheduleObject, convertLocalTimeToUTC } from '@/lib/utils';

interface Props {
  user: User | null;
}

export default function UserProfile({ user: userProp }: Props) {
  const { user: authUser, refreshUser } = useAuth();
  const user = userProp || authUser;
  
  const [formData, setFormData] = useState({
    name: user?.name || '',
    xml_endpoint: user?.xml_endpoint || '',
    xml_token: user?.xml_token || '',
    report_enabled: user?.report_enabled || false,
  });
  const [schedule, setSchedule] = useState<ReportSchedule>({
    frequency: 'daily',
    time: '09:00',
  });
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (user) {
      setFormData({
        name: user.name || '',
        xml_endpoint: user.xml_endpoint || '',
        xml_token: user.xml_token || '',
        report_enabled: user.report_enabled || false,
      });
      
      const parsedSchedule = parseReportScheduleObject(user.report_schedule || null);
      if (parsedSchedule) {
        setSchedule(parsedSchedule);
      }
    }
  }, [user]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage(null);
    setLoading(true);

    try {
      const utcTime = convertLocalTimeToUTC(schedule.time);
      const scheduleData: ReportSchedule = {
        ...schedule,
        time: utcTime,
      };

      if (schedule.frequency === 'weekly') {
        scheduleData.day_of_week = parseInt((document.getElementById('profileWeeklyDay') as HTMLSelectElement)?.value || '1');
      } else if (schedule.frequency === 'monthly') {
        scheduleData.day_of_month = parseInt((document.getElementById('profileMonthlyDay') as HTMLSelectElement)?.value || '1');
      }

      await profileApi.update({
        ...formData,
        report_schedule: JSON.stringify(scheduleData),
      });
      
      setMessage({ type: 'success', text: 'Profilo aggiornato con successo!' });
      await refreshUser();
      
      setTimeout(() => setMessage(null), 5000);
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Errore durante l\'aggiornamento' });
    } finally {
      setLoading(false);
    }
  };

  if (!user) return null;

  return (
    <div className="card">
      <h3 className="text-2xl font-semibold text-gray-800 mb-4">Il Mio Profilo</h3>

      {message && (
        <div className={`px-4 py-3 rounded-lg mb-4 ${
          message.type === 'success' 
            ? 'bg-green-50 border border-green-200 text-green-700'
            : 'bg-red-50 border border-red-200 text-red-700'
        }`}>
          {message.text}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div className="mb-4">
          <label className="block text-gray-700 font-medium mb-2">Nome</label>
          <input
            type="text"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            required
            className="input"
            disabled={loading}
          />
        </div>

        <div className="mb-4">
          <label className="block text-gray-700 font-medium mb-2">Email</label>
          <input
            type="email"
            value={user.email}
            disabled
            className="input bg-gray-100"
          />
        </div>

        <div className="mb-4">
          <label className="block text-gray-700 font-medium mb-2">XML Endpoint URL</label>
          <input
            type="url"
            value={formData.xml_endpoint}
            onChange={(e) => setFormData({ ...formData, xml_endpoint: e.target.value })}
            className="input"
            disabled={loading}
            placeholder="https://api.example.com/data"
          />
        </div>

        <div className="mb-4">
          <label className="block text-gray-700 font-medium mb-2">XML Token (Opzionale)</label>
          <input
            type="text"
            value={formData.xml_token}
            onChange={(e) => setFormData({ ...formData, xml_token: e.target.value })}
            className="input"
            disabled={loading}
            placeholder="Bearer token o auth key"
          />
        </div>

        <div className="mb-4">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={formData.report_enabled}
              onChange={(e) => setFormData({ ...formData, report_enabled: e.target.checked })}
              className="w-4 h-4"
              disabled={loading}
            />
            <span className="text-gray-700 font-medium">Abilita Report Automatici</span>
          </label>
        </div>

        <div className="mb-4">
          <label className="block text-gray-700 font-medium mb-2">Periodicità Report</label>
          <select
            value={schedule.frequency}
            onChange={(e) => setSchedule({ ...schedule, frequency: e.target.value as any })}
            className="input"
            disabled={loading}
          >
            <option value="daily">Giornaliero</option>
            <option value="weekly">Settimanale</option>
            <option value="monthly">Mensile</option>
          </select>
        </div>

        <div className="mb-4">
          <label className="block text-gray-700 font-medium mb-2">Ora Invio Report</label>
          <input
            type="time"
            value={schedule.time}
            onChange={(e) => setSchedule({ ...schedule, time: e.target.value })}
            className="input"
            disabled={loading}
          />
        </div>

        {schedule.frequency === 'weekly' && (
          <div className="mb-4">
            <label className="block text-gray-700 font-medium mb-2">Giorno della Settimana</label>
            <select 
              id="profileWeeklyDay" 
              defaultValue={schedule.day_of_week?.toString() || '1'}
              className="input" 
              disabled={loading}
            >
              <option value="1">Lunedì</option>
              <option value="2">Martedì</option>
              <option value="3">Mercoledì</option>
              <option value="4">Giovedì</option>
              <option value="5">Venerdì</option>
              <option value="6">Sabato</option>
              <option value="0">Domenica</option>
            </select>
          </div>
        )}

        {schedule.frequency === 'monthly' && (
          <div className="mb-4">
            <label className="block text-gray-700 font-medium mb-2">Giorno del Mese</label>
            <select 
              id="profileMonthlyDay" 
              defaultValue={schedule.day_of_month?.toString() || '1'}
              className="input" 
              disabled={loading}
            >
              {Array.from({ length: 28 }, (_, i) => i + 1).map((day) => (
                <option key={day} value={day}>{day}</option>
              ))}
            </select>
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="btn btn-primary w-full"
        >
          {loading ? 'Aggiornamento...' : 'Aggiorna Profilo'}
        </button>
      </form>
    </div>
  );
}

