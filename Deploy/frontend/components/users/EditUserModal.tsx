'use client';

import { useState } from 'react';
import { usersApi } from '@/lib/api';
import { User } from '@/types';
import ConnectorManagement from './ConnectorManagement';

interface Props {
  user: User;
  onClose: () => void;
  onSuccess: () => void;
}

export default function EditUserModal({ user, onClose, onSuccess }: Props) {
  const [formData, setFormData] = useState({
    name: user.name || '',
    email: user.email,
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await usersApi.update(user.user_id, {
        name: formData.name,
      });
      onSuccess();
    } catch (err: any) {
      setError(err.message || 'Errore nell\'aggiornamento dell\'utente');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="card max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <h3 className="text-2xl font-semibold text-gray-800 mb-4">Modifica Utente</h3>

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
            <label className="block text-gray-700 font-medium mb-2">Email</label>
            <input
              type="email"
              value={formData.email}
              disabled
              className="input bg-gray-100"
            />
            <small className="text-gray-500 text-sm mt-1 block">
              Email per ricevere i report automatici (non modificabile)
            </small>
          </div>

          <div className="mb-6">
            <button
              type="submit"
              disabled={loading}
              className="btn btn-primary w-full"
            >
              {loading ? 'Salvataggio...' : 'Salva Modifiche'}
            </button>
          </div>
        </form>

        <div className="border-t pt-6 mt-6">
          <ConnectorManagement userId={user.user_id} onUpdate={onSuccess} />
        </div>

        <div className="mt-6">
          <button
            type="button"
            onClick={onClose}
            className="btn btn-secondary w-full"
            disabled={loading}
          >
            Chiudi
          </button>
        </div>
      </div>
    </div>
  );
}

