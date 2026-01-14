'use client';

import { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';

interface LoginFormProps {
  onForgotPassword: () => void;
}

export default function LoginForm({ onForgotPassword }: LoginFormProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await login(email, password);
    } catch (err: any) {
      let errorMessage = 'Errore durante l\'accesso';
      
      if (err.code === 'NotAuthorizedException') {
        errorMessage = 'Email o password non corretti';
      } else if (err.code === 'UserNotFoundException') {
        errorMessage = 'Utente non trovato';
      } else if (err.code === 'UserNotConfirmedException') {
        errorMessage = 'Account non confermato';
      } else if (err.message) {
        errorMessage = err.message;
      }
      
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-[#eeeeee]">
      <div className="w-full max-w-md bg-[#286291] rounded-lg shadow-xl p-8">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-light text-white mb-2">Maya</h1>
          <p className="text-white/90 text-sm leading-relaxed">
            Analytics<br />
            Assistant per<br />
            Selera Centralino
          </p>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="mb-5">
            <label className="block text-white font-medium mb-2">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:outline-none focus:border-[#113357] transition-colors bg-white text-gray-800"
              disabled={loading}
            />
          </div>

          <div className="mb-5">
            <div className="flex justify-between items-center mb-2">
              <label className="block text-white font-medium">Password</label>
              <button
                type="button"
                onClick={onForgotPassword}
                disabled={loading}
                className="text-sm text-white/80 hover:text-white underline focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Password dimenticata?
              </button>
            </div>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:outline-none focus:border-[#113357] transition-colors bg-white text-gray-800"
              disabled={loading}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full px-4 py-3 rounded-lg font-semibold transition-all duration-200 bg-gradient-to-r from-[#113357] to-[#286291] text-white hover:shadow-lg hover:-translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0"
          >
            {loading ? 'Accesso in corso...' : 'Accedi'}
          </button>
        </form>
      </div>
    </div>
  );
}

