'use client';

import { useState } from 'react';
import { usersApi } from '@/lib/api';
import { CreateUserInput, ReportSchedule } from '@/types';
import { convertLocalTimeToUTC } from '@/lib/utils';

interface Props {
  tenantId: string;
  onClose: () => void;
  onSuccess: () => void;
}

export default function CreateUserModal({ tenantId, onClose, onSuccess }: Props) {
  const [formData, setFormData] = useState<CreateUserInput & { connector_name?: string }>({
    name: '',
    email: '',
    xml_endpoint: '',
    xml_token: '',
    connector_name: '',
  });
  const [schedule, setSchedule] = useState<ReportSchedule>({
    frequency: 'daily',
    time: '09:00',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const utcTime = convertLocalTimeToUTC(schedule.time);
      const scheduleData: ReportSchedule = {
        ...schedule,
        time: utcTime,
      };

      if (schedule.frequency === 'weekly') {
        scheduleData.day_of_week = parseInt((document.getElementById('userWeeklyDay') as HTMLSelectElement)?.value || '1');
      } else if (schedule.frequency === 'monthly') {
        scheduleData.day_of_month = parseInt((document.getElementById('userMonthlyDay') as HTMLSelectElement)?.value || '1');
      }

      const payload: any = {
        name: formData.name,
        email: formData.email,
      };

      // If XML endpoint provided, include connector data
      if (formData.xml_endpoint) {
        payload.xml_endpoint = formData.xml_endpoint;
        payload.xml_token = formData.xml_token || '';
        payload.connector_name = formData.connector_name || 'Report Principale';
        payload.report_schedule = JSON.stringify(scheduleData);
      }

      await usersApi.create(tenantId, payload);
      onSuccess();
    } catch (err: any) {
      setError(err.message || 'Errore nella creazione dell\'utente');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="card max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <h3 className="text-2xl font-semibold text-gray-800 mb-4">Crea Nuovo Utente</h3>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4">
            {error}
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
            <label className="block text-gray-700 font-medium mb-2">Email per Report</label>
            <input
              type="email"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              required
              className="input"
              disabled={loading}
              placeholder="supervisore@azienda.com"
            />
            <small className="text-gray-500 text-sm mt-1 block">
              Email dove ricevere i report automatici. Può essere duplicata tra più utenti.
            </small>
          </div>

          <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <p className="text-sm text-blue-800 mb-2">
              <strong>Nota:</strong> L'utente riceverà solo email automatiche. Non può accedere al sistema.
            </p>
            <p className="text-sm text-blue-700">
              I connettori XML possono essere aggiunti dopo la creazione dell'utente.
            </p>
          </div>

          <div className="mb-4">
            <label className="block text-gray-700 font-medium mb-2">XML Endpoint URL (Opzionale)</label>
            <input
              type="url"
              value={formData.xml_endpoint}
              onChange={(e) => setFormData({ ...formData, xml_endpoint: e.target.value })}
              className="input"
              disabled={loading}
              placeholder="https://api.example.com/data"
            />
            <small className="text-gray-500 text-sm mt-1 block">
              Puoi aggiungere connettori XML dopo la creazione dell'utente.
            </small>
          </div>

          {formData.xml_endpoint && (
            <>
              <div className="mb-4">
                <label className="block text-gray-700 font-medium mb-2">Nome Connettore</label>
                <input
                  type="text"
                  value={formData.connector_name || ''}
                  onChange={(e) => setFormData({ ...formData, connector_name: e.target.value })}
                  className="input"
                  disabled={loading}
                  placeholder="Report IVR Principale"
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
                  <select id="userWeeklyDay" className="input" disabled={loading}>
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
                  <select id="userMonthlyDay" className="input" disabled={loading}>
                    {Array.from({ length: 28 }, (_, i) => i + 1).map((day) => (
                      <option key={day} value={day}>{day}</option>
                    ))}
                  </select>
                </div>
              )}
            </>
          )}

          <div className="flex gap-2">
            <button
              type="submit"
              disabled={loading}
              className="btn btn-primary flex-1"
            >
              {loading ? 'Creazione in corso...' : 'Crea Utente'}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="btn btn-secondary"
              disabled={loading}
            >
              Annulla
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

