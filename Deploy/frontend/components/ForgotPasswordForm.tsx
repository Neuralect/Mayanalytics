'use client';

import { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';

interface ForgotPasswordFormProps {
  onBack: () => void;
}

export default function ForgotPasswordForm({ onBack }: ForgotPasswordFormProps) {
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmNewPassword, setConfirmNewPassword] = useState('');
  const [step, setStep] = useState<'request' | 'confirm'>('request');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const { forgotPassword, confirmPassword } = useAuth();

  const handleRequestReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setLoading(true);

    try {
      await forgotPassword(email);
      setSuccess('Codice di verifica inviato alla tua email. Controlla la posta e inserisci il codice ricevuto.');
      setStep('confirm');
    } catch (err: any) {
      let errorMessage = 'Errore durante la richiesta di reset password';
      
      if (err.code === 'UserNotFoundException') {
        errorMessage = 'Utente non trovato';
      } else if (err.code === 'LimitExceededException') {
        errorMessage = 'Troppi tentativi. Riprova più tardi';
      } else if (err.message) {
        errorMessage = err.message;
      }
      
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (newPassword !== confirmNewPassword) {
      setError('Le password non corrispondono');
      return;
    }

    if (newPassword.length < 8) {
      setError('La password deve essere di almeno 8 caratteri');
      return;
    }

    setLoading(true);

    try {
      await confirmPassword(email, code, newPassword);
      setSuccess('Password reimpostata con successo! Ora puoi effettuare il login.');
      setTimeout(() => {
        onBack();
      }, 2000);
    } catch (err: any) {
      let errorMessage = 'Errore durante il reset password';
      
      if (err.code === 'CodeMismatchException') {
        errorMessage = 'Codice di verifica non valido';
      } else if (err.code === 'ExpiredCodeException') {
        errorMessage = 'Codice di verifica scaduto. Richiedi un nuovo codice';
      } else if (err.code === 'InvalidPasswordException') {
        errorMessage = 'Password non valida. Deve contenere almeno 8 caratteri, una maiuscola e un numero';
      } else if (err.message) {
        errorMessage = err.message;
      }
      
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  if (step === 'request') {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <div className="card w-full max-w-md">
          <div className="text-center mb-8">
            <h1 className="text-4xl font-light text-gray-800 mb-2">🤖 Maya</h1>
            <p className="text-gray-600">Password Dimenticata</p>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4">
              {error}
            </div>
          )}

          <form onSubmit={handleRequestReset}>
            <div className="mb-5">
              <label className="block text-gray-700 font-medium mb-2">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="input"
                disabled={loading}
                placeholder="Inserisci la tua email"
              />
              <small className="text-gray-500 text-sm mt-1 block">
                Ti invieremo un codice di verifica per reimpostare la password
              </small>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn btn-primary w-full mb-3"
            >
              {loading ? 'Invio in corso...' : 'Invia codice di verifica'}
            </button>

            <button
              type="button"
              onClick={onBack}
              disabled={loading}
              className="btn btn-secondary w-full"
            >
              Torna al login
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="card w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-light text-gray-800 mb-2">🤖 Maya</h1>
          <p className="text-gray-600">Reimposta Password</p>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4">
            {error}
          </div>
        )}

        {success && (
          <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg mb-4">
            {success}
          </div>
        )}

        <form onSubmit={handleConfirmReset}>
          <div className="mb-5">
            <label className="block text-gray-700 font-medium mb-2">Codice di verifica</label>
            <input
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\s/g, ''))}
              required
              className="input"
              disabled={loading}
              placeholder="Inserisci il codice ricevuto via email"
              maxLength={6}
            />
          </div>

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
              placeholder="Inserisci la nuova password"
            />
            <small className="text-gray-500 text-sm mt-1 block">
              Minimo 8 caratteri, almeno una maiuscola e un numero
            </small>
          </div>

          <div className="mb-5">
            <label className="block text-gray-700 font-medium mb-2">Conferma Password</label>
            <input
              type="password"
              value={confirmNewPassword}
              onChange={(e) => setConfirmNewPassword(e.target.value)}
              required
              minLength={8}
              className="input"
              disabled={loading}
              placeholder="Conferma la nuova password"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn btn-primary w-full mb-3"
          >
            {loading ? 'Reimpostazione in corso...' : 'Reimposta Password'}
          </button>

          <button
            type="button"
            onClick={() => {
              setStep('request');
              setCode('');
              setNewPassword('');
              setConfirmNewPassword('');
              setError('');
              setSuccess('');
            }}
            disabled={loading}
            className="btn btn-secondary w-full"
          >
            Richiedi nuovo codice
          </button>
        </form>
      </div>
    </div>
  );
}

