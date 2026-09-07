import React, { useState } from 'react';
import { LockClosedIcon } from '@heroicons/react/24/outline';
import { login, register } from '../services/api';

interface AuthPanelProps {
  onAuthenticated: () => void;
}

const AuthPanel: React.FC<AuthPanelProps> = ({ onAuthenticated }) => {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      if (mode === 'login') await login(username, password);
      else await register(username, password);
      onAuthenticated();
    } catch (requestError) {
      const detail = (requestError as { response?: { data?: { detail?: string; password?: string[] } } })
        .response?.data;
      setError(detail?.detail || detail?.password?.[0] || 'The account details could not be accepted.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md rounded-2xl border border-gray-200 bg-white p-8 shadow-sm">
        <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-xl bg-primary-50">
          <LockClosedIcon className="h-6 w-6 text-primary-600" />
        </div>
        <h1 className="text-2xl font-bold text-gray-900">File Vault System</h1>
        <p className="mt-2 text-sm text-gray-500">
          Sign in to search and manage only your own file references.
        </p>
        <form className="mt-6 space-y-4" onSubmit={submit}>
          <label className="block text-sm font-medium text-gray-700">
            Username
            <input
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
              required
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
            />
          </label>
          <label className="block text-sm font-medium text-gray-700">
            Password
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              required
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
            />
          </label>
          {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
          <button
            disabled={submitting}
            className="w-full rounded-lg bg-primary-600 px-4 py-2 font-medium text-white hover:bg-primary-700 disabled:opacity-60"
          >
            {submitting ? 'Please wait...' : mode === 'login' ? 'Sign in' : 'Create account'}
          </button>
        </form>
        <button
          onClick={() => {
            setMode(mode === 'login' ? 'register' : 'login');
            setError('');
          }}
          className="mt-4 w-full text-sm font-medium text-primary-600 hover:text-primary-700"
        >
          {mode === 'login' ? 'Create a new account' : 'Already have an account? Sign in'}
        </button>
      </div>
    </main>
  );
};

export default AuthPanel;
