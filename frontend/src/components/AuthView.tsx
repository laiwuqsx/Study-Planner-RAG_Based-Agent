import { FormEvent } from 'react';

import { AuthMode } from '../types';

type AuthViewProps = {
  authMode: AuthMode;
  username: string;
  password: string;
  loading: boolean;
  onSubmit: (event: FormEvent) => void;
  onUsernameChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onToggleMode: () => void;
};

export function AuthView({
  authMode,
  username,
  password,
  loading,
  onSubmit,
  onUsernameChange,
  onPasswordChange,
  onToggleMode,
}: AuthViewProps) {
  return (
    <section className="auth-layout">
      <div className="auth-copy">
        <h2>{authMode === 'login' ? 'Log in' : 'Create account'}</h2>
        <p>Access your courses and manage study materials in a student-scoped workspace.</p>
      </div>
      <form className="panel form-stack" onSubmit={onSubmit}>
        <label>
          Username
          <input value={username} onChange={(event) => onUsernameChange(event.target.value)} required />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(event) => onPasswordChange(event.target.value)}
            required
          />
        </label>
        <button type="submit" disabled={loading}>
          {loading ? 'Working...' : authMode === 'login' ? 'Log in' : 'Register'}
        </button>
        <button type="button" className="link-button" onClick={onToggleMode}>
          {authMode === 'login' ? 'Need an account? Register' : 'Already have an account? Log in'}
        </button>
      </form>
    </section>
  );
}
