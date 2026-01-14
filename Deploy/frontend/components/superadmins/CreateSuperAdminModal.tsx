'use client';

import { useState } from 'react';
import { superadminsApi } from '@/lib/api';
import { CreateSuperAdminInput } from '@/types';

interface Props {
  onClose: () => void;
  onSuccess: () => void;
}

export default function CreateSuperAdminModal({ onClose, onSuccess }: Props) {
  const [formData, setFormData] = useState<CreateSuperAdminInput>({
    name: '',
    email: '',
    password: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await superadminsApi.create(formData);
      onSuccess();
    } catch (err: any) {
      setError(err.message || 'Errore nella creazione del superadmin');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 modal-backdrop flex items-center justify-center z-50 p-4">
      <div className="card max-w-md w-full max-h-[90vh] overflow-y-auto">
        <h3 className="text-2xl font-semibold text-gray-800 mb-4">Crea Nuovo SuperAdmin</h3>

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
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              required
              className="input"
              disabled={loading}
            />
            <small className="text-gray-500 text-sm mt-1 block">
              Email per login (deve essere univoca)
            </small>
          </div>

          <div className="mb-4">
            <label className="block text-gray-700 font-medium mb-2">Password</label>
            <input
              type="password"
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              required
              minLength={8}
              className="input"
              disabled={loading}
            />
            <small className="text-gray-500 text-sm mt-1 block">
              Minimo 8 caratteri, almeno una maiuscola e un numero
            </small>
          </div>

          <div className="flex gap-2">
            <button
              type="submit"
              disabled={loading}
              className="btn bg-[#286291] hover:bg-[#113357] text-white flex-1"
            >
              {loading ? 'Creazione in corso...' : 'Crea SuperAdmin'}
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

