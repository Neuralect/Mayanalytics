'use client';

import { useState } from 'react';
import { CognitoUser } from 'amazon-cognito-identity-js';
import Image from 'next/image';

interface ResetPasswordFormProps {
  email: string;
  cognitoUser: CognitoUser;
  onBack: () => void;
  onSuccess: () => void;
}

export default function ResetPasswordForm({ email, cognitoUser, onBack, onSuccess }: ResetPasswordFormProps) {
  const [verificationCode, setVerificationCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // Validazione password
    if (newPassword !== confirmPassword) {
      setError('Le password non corrispondono');
      return;
    }

    if (newPassword.length < 8) {
      setError('La password deve essere di almeno 8 caratteri');
      return;
    }

    // Validazione requisiti password (almeno una maiuscola e un numero)
    const hasUpperCase = /[A-Z]/.test(newPassword);
    const hasNumber = /[0-9]/.test(newPassword);
    
    if (!hasUpperCase || !hasNumber) {
      setError('La password deve contenere almeno una maiuscola e un numero');
      return;
    }

    setLoading(true);

    try {
      cognitoUser.confirmPassword(verificationCode, newPassword, {
        onSuccess: () => {
          // Password resettata con successo
          onSuccess();
        },
        onFailure: (err: any) => {
          let errorMessage = 'Errore durante il reset della password';
          
          if (err.code === 'CodeMismatchException') {
            errorMessage = 'Codice di verifica non valido';
          } else if (err.code === 'ExpiredCodeException') {
            errorMessage = 'Codice di verifica scaduto. Richiedi un nuovo codice';
          } else if (err.code === 'InvalidPasswordException') {
            errorMessage = 'La password non rispetta i requisiti di sicurezza';
          } else if (err.message) {
            errorMessage = err.message;
          }
          
          setError(errorMessage);
          setLoading(false);
        },
      });
    } catch (err: any) {
      setError(err.message || 'Errore durante il reset della password');
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
          <h2 className="text-2xl font-light text-gray-800">Reimposta Password</h2>
          <p className="text-sm text-gray-600 mt-2">
            Inserisci il codice di verifica inviato a <strong>{email}</strong>
          </p>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="mb-5">
            <label className="block text-gray-800 font-medium mb-2">
              Codice di verifica
            </label>
            <input
              type="text"
              value={verificationCode}
              onChange={(e) => setVerificationCode(e.target.value)}
              required
              className="w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:outline-none focus:border-[#113357] transition-colors bg-white text-gray-800"
              disabled={loading}
              placeholder="Inserisci il codice"
              maxLength={6}
            />
          </div>

          <div className="mb-5">
            <label className="block text-gray-800 font-medium mb-2">
              Nuova Password
            </label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              minLength={8}
              className="w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:outline-none focus:border-[#113357] transition-colors bg-white text-gray-800"
              disabled={loading}
              placeholder="Inserisci la nuova password"
            />
            <small className="text-gray-600 text-sm mt-2 block">
              Minimo 8 caratteri, almeno una maiuscola e un numero
            </small>
          </div>

          <div className="mb-5">
            <label className="block text-gray-800 font-medium mb-2">
              Conferma Password
            </label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              minLength={8}
              className="w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:outline-none focus:border-[#113357] transition-colors bg-white text-gray-800"
              disabled={loading}
              placeholder="Conferma la nuova password"
            />
          </div>

          <div className="flex gap-3">
            <button
              type="button"
              onClick={onBack}
              disabled={loading}
              className="flex-1 px-4 py-3 rounded-lg font-semibold transition-all duration-200 bg-[#286291] text-white hover:bg-[#113357] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Indietro
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 px-4 py-3 rounded-lg font-semibold transition-all duration-200 bg-gradient-to-r from-[#113357] to-[#286291] text-white hover:shadow-lg hover:-translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Reset in corso...' : 'Reimposta Password'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
