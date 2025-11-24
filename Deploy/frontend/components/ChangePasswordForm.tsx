'use client';

import { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';

export default function ChangePasswordForm() {
  const [newPassword, setNewPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { changePassword } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await changePassword(newPassword);
    } catch (err: any) {
      setError(err.message || 'Errore durante il cambio password');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="card w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-light text-gray-800 mb-2">🤖 Maya</h1>
          <p className="text-gray-600">Cambio Password Obbligatorio</p>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="mb-5">
            <label className="block text-gray-700 font-medium mb-2">Nuova Password</label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              minLength={8}
              className="input"
              disabled={loading}
            />
            <small className="text-gray-500 text-sm mt-1 block">
              Minimo 8 caratteri, almeno una maiuscola e un numero
            </small>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn btn-primary w-full"
          >
            {loading ? 'Cambio password...' : 'Cambia Password'}
          </button>
        </form>
      </div>
    </div>
  );
}

