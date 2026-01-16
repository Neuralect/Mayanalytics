'use client';

import { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import Image from 'next/image';

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
    <div className="min-h-screen flex items-center justify-center p-4 bg-[#eeeeee]">
      <div className="w-full max-w-md bg-white rounded-lg shadow-2xl p-8">
        <div className="text-center mb-8">
          <div className="flex justify-center mb-6">
            <Image
              src="/images/logo.svg"
              alt="Logo"
              width={300}
              height={300}
              className="object-contain"
              priority
            />
          </div>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="mb-5">
            <label className="block text-gray-800 font-medium mb-2">Nuova Password</label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              minLength={8}
              className="w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:outline-none focus:border-[#113357] transition-colors bg-white text-gray-800"
              disabled={loading}
            />
            <small className="text-gray-500 text-sm mt-1 block">
              Minimo 8 caratteri, almeno una maiuscola e un numero
            </small>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full px-4 py-3 rounded-lg font-semibold transition-all duration-200 bg-gradient-to-r from-[#113357] to-[#286291] text-white hover:shadow-lg hover:-translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Cambio password...' : 'Cambia Password'}
          </button>
        </form>
      </div>
    </div>
  );
}

