'use client';

import { useState, useEffect } from 'react';
import { connectorsApi } from '@/lib/api';
import { ReportSchedule } from '@/types';
import { convertLocalTimeToUTC } from '@/lib/utils';

interface Connector {
  connector_id: string;
  name: string;
  xml_endpoint: string;
  xml_token?: string;
  report_enabled: boolean;
  report_schedule?: string;
}

interface Props {
  userId: string;
  onUpdate?: () => void;
}

export default function ConnectorManagement({ userId, onUpdate }: Props) {
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [loading, setLoading] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingConnector, setEditingConnector] = useState<Connector | null>(null);

  useEffect(() => {
    loadConnectors();
  }, [userId]);

  const loadConnectors = async () => {
    try {
      setLoading(true);
      const res = await connectorsApi.list(userId);
      setConnectors(res.connectors || []);
    } catch (err: any) {
      console.error('Error loading connectors:', err);
      setConnectors([]);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (connectorId: string) => {
    if (!confirm('Sei sicuro di voler eliminare questo connettore?')) {
      return;
    }

    try {
      await connectorsApi.delete(userId, connectorId);
      await loadConnectors();
      onUpdate?.();
    } catch (err: any) {
      alert('Errore durante l\'eliminazione: ' + err.message);
    }
  };

  const handleEdit = (connector: Connector) => {
    setEditingConnector(connector);
    setShowAddModal(true);
  };

  const handleClose = () => {
    setShowAddModal(false);
    setEditingConnector(null);
  };

  const handleSuccess = () => {
    loadConnectors();
    onUpdate?.();
    handleClose();
  };

  if (loading) {
    return <div className="text-center py-4 text-gray-500">Caricamento connettori...</div>;
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h4 className="text-lg font-semibold text-gray-800">Connettori XML</h4>
        <button
          onClick={() => setShowAddModal(true)}
          className="btn btn-small bg-blue-500 hover:bg-blue-600 text-white"
        >
          + Aggiungi Connettore
        </button>
      </div>

      {connectors.length === 0 ? (
        <div className="text-center py-8 text-gray-500 bg-gray-50 rounded-lg">
          <p>Nessun connettore configurato</p>
          <p className="text-sm mt-2">Aggiungi un connettore per abilitare i report automatici</p>
        </div>
      ) : (
        <div className="space-y-3">
          {connectors.map((connector) => {
            const schedule = connector.report_schedule 
              ? JSON.parse(connector.report_schedule) 
              : { frequency: 'daily', time: '09:00' };
            
            return (
              <div key={connector.connector_id} className="border rounded-lg p-4 bg-white">
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <h5 className="font-semibold text-gray-800">{connector.name}</h5>
                      <span className={`badge ${connector.report_enabled ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}`}>
                        {connector.report_enabled ? 'Attivo' : 'Disattivo'}
                      </span>
                    </div>
                    <p className="text-sm text-gray-600 mb-1">
                      <strong>Endpoint:</strong> {connector.xml_endpoint}
                    </p>
                    {connector.xml_token && (
                      <p className="text-sm text-gray-600 mb-1">
                        <strong>Token:</strong> {connector.xml_token.substring(0, 20)}...
                      </p>
                    )}
                    <p className="text-sm text-gray-600">
                      <strong>Schedulazione:</strong> {schedule.frequency === 'daily' ? 'Giornaliero' : schedule.frequency === 'weekly' ? 'Settimanale' : 'Mensile'} alle {schedule.time}
                    </p>
                  </div>
                  <div className="flex gap-2 ml-4">
                    <button
                      onClick={() => handleEdit(connector)}
                      className="btn btn-small bg-blue-500 hover:bg-blue-600 text-white"
                    >
                      Modifica
                    </button>
                    <button
                      onClick={() => handleDelete(connector.connector_id)}
                      className="btn btn-small btn-danger"
                    >
                      Elimina
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {showAddModal && (
        <ConnectorModal
          userId={userId}
          connector={editingConnector}
          onClose={handleClose}
          onSuccess={handleSuccess}
        />
      )}
    </div>
  );
}

interface ConnectorModalProps {
  userId: string;
  connector?: Connector | null;
  onClose: () => void;
  onSuccess: () => void;
}

function ConnectorModal({ userId, connector, onClose, onSuccess }: ConnectorModalProps) {
  const [formData, setFormData] = useState({
    name: connector?.name || '',
    xml_endpoint: connector?.xml_endpoint || '',
    xml_token: connector?.xml_token || '',
    report_enabled: connector?.report_enabled ?? true,
  });
  const [schedule, setSchedule] = useState<ReportSchedule>(() => {
    if (connector?.report_schedule) {
      const parsed = JSON.parse(connector.report_schedule);
      return {
        frequency: parsed.frequency || 'daily',
        time: parsed.time || '09:00',
        day_of_week: parsed.day_of_week,
        day_of_month: parsed.day_of_month,
      };
    }
    return { frequency: 'daily', time: '09:00' };
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
        scheduleData.day_of_week = parseInt((document.getElementById('connectorWeeklyDay') as HTMLSelectElement)?.value || '1');
      } else if (schedule.frequency === 'monthly') {
        scheduleData.day_of_month = parseInt((document.getElementById('connectorMonthlyDay') as HTMLSelectElement)?.value || '1');
      }

      const payload = {
        ...formData,
        report_schedule: JSON.stringify(scheduleData),
      };

      if (connector) {
        await connectorsApi.update(userId, connector.connector_id, payload);
      } else {
        await connectorsApi.create(userId, payload);
      }

      onSuccess();
    } catch (err: any) {
      setError(err.message || 'Errore durante il salvataggio');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="card max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <h3 className="text-2xl font-semibold text-gray-800 mb-4">
          {connector ? 'Modifica Connettore' : 'Aggiungi Connettore'}
        </h3>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="block text-gray-700 font-medium mb-2">Nome Connettore</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              required
              className="input"
              disabled={loading}
              placeholder="Report IVR Principale"
            />
          </div>

          <div className="mb-4">
            <label className="block text-gray-700 font-medium mb-2">XML Endpoint URL</label>
            <input
              type="url"
              value={formData.xml_endpoint}
              onChange={(e) => setFormData({ ...formData, xml_endpoint: e.target.value })}
              required
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
              <span className="text-gray-700 font-medium">Report Abilitato</span>
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
                id="connectorWeeklyDay" 
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
                id="connectorMonthlyDay" 
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

          <div className="flex gap-2">
            <button
              type="submit"
              disabled={loading}
              className="btn btn-primary flex-1"
            >
              {loading ? 'Salvataggio...' : connector ? 'Salva Modifiche' : 'Aggiungi Connettore'}
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

