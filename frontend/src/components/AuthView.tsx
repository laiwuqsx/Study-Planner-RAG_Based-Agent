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
        <p className="eyebrow">Personal Study System</p>
        <h2>{authMode === 'login' ? 'Log in' : 'Create account'}</h2>
        <p>Access your courses, materials, topic review flows, and study plans in a single focused workspace.</p>
        <div className="feature-list">
          <div className="feature-item">
            <strong>Structured workspace</strong>
            <span>Keep courses, documents, and progress in one place.</span>
          </div>
          <div className="feature-item">
            <strong>Topic-centered learning</strong>
            <span>Review extracted topics with supporting source chunks and grounded Q&amp;A.</span>
          </div>
          <div className="feature-item">
            <strong>Actionable planning</strong>
            <span>Turn course content into a study plan you can actually execute.</span>
          </div>
        </div>
      </div>
      <form className="panel form-stack auth-panel" onSubmit={onSubmit}>
        <div className="page-header compact">
          <div>
            <p className="eyebrow">Account</p>
            <h2>{authMode === 'login' ? 'Welcome back' : 'Set up your workspace'}</h2>
          </div>
        </div>
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
        <button type="button" className="secondary-button" onClick={onToggleMode}>
          {authMode === 'login' ? 'Need an account? Register' : 'Already have an account? Log in'}
        </button>
      </form>
    </section>
  );
}
