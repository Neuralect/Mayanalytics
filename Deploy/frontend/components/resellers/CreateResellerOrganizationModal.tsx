'use client';

import { useState } from 'react';
import { resellerOrganizationsApi } from '@/lib/api';
import { CreateResellerOrganizationInput } from '@/types';

interface Props {
  onClose: () => void;
  onSuccess: () => void;
}

export default function CreateResellerOrganizationModal({ onClose, onSuccess }: Props) {
  const [formData, setFormData] = useState<CreateResellerOrganizationInput>({
    name: '',
    description: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await resellerOrganizationsApi.create(formData);
      onSuccess();
    } catch (err: any) {
      setError(err.message || 'Errore nella creazione del ruolo reseller');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="card max-w-md w-full max-h-[90vh] overflow-y-auto">
        <h3 className="text-2xl font-semibold text-gray-800 mb-4">Crea Ruolo Reseller</h3>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="block text-gray-700 font-medium mb-2">Nome Ruolo Reseller</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              required
              className="input"
              disabled={loading}
              placeholder="Es: Reseller Italia Nord"
            />
          </div>

          <div className="mb-4">
            <label className="block text-gray-700 font-medium mb-2">Descrizione (opzionale)</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              className="input"
              disabled={loading}
              rows={3}
              placeholder="Descrizione del ruolo reseller..."
            />
          </div>

          <div className="flex gap-2">
            <button
              type="submit"
              disabled={loading}
              className="btn btn-primary flex-1"
            >
              {loading ? 'Creazione in corso...' : 'Crea Ruolo Reseller'}
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

