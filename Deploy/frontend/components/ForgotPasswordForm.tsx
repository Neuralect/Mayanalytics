'use client';

import { useState } from 'react';
import { CognitoUser } from 'amazon-cognito-identity-js';
import { userPool } from '@/lib/cognito';
import Image from 'next/image';

interface ForgotPasswordFormProps {
  onBack: () => void;
  onCodeSent: (email: string, cognitoUser: CognitoUser) => void;
}

export default function ForgotPasswordForm({ onBack, onCodeSent }: ForgotPasswordFormProps) {
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const userData = {
        Username: email,
        Pool: userPool,
      };
      const cognitoUser = new CognitoUser(userData);

      cognitoUser.forgotPassword({
        onSuccess: (data) => {
          // Codice inviato con successo
          onCodeSent(email, cognitoUser);
        },
        onFailure: (err: any) => {
          let errorMessage = 'Errore durante la richiesta di reset password';
          
          if (err.code === 'UserNotFoundException') {
            errorMessage = 'Utente non trovato';
          } else if (err.code === 'LimitExceededException') {
            errorMessage = 'Troppi tentativi. Riprova più tardi';
          } else if (err.message) {
            errorMessage = err.message;
          }
          
          setError(errorMessage);
          setLoading(false);
        },
      });
    } catch (err: any) {
      setError(err.message || 'Errore durante la richiesta di reset password');
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
          <h2 className="text-2xl font-light text-gray-800">Password Dimenticata</h2>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="mb-5">
            <label className="block text-gray-800 font-medium mb-2">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:outline-none focus:border-[#113357] transition-colors bg-white text-gray-800"
              disabled={loading}
              placeholder="nome@esempio.com"
            />
            <small className="text-gray-600 text-sm mt-2 block">
              Ti invieremo un codice di verifica per reimpostare la password
            </small>
          </div>

          <div className="flex gap-3">
            <button
              type="button"
              onClick={onBack}
              disabled={loading}
              className="flex-1 px-4 py-3 rounded-lg font-semibold transition-all duration-200 bg-[#286291] text-white hover:bg-[#113357] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Torna al login
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 px-4 py-3 rounded-lg font-semibold transition-all duration-200 bg-gradient-to-r from-[#113357] to-[#286291] text-white hover:shadow-lg hover:-translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Invio in corso...' : 'Invia codice di verifica'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}










