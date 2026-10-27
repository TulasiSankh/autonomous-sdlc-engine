import React, { useState } from 'react';
import type { TaskRecord } from '../types/api';
import { RobotAvatar } from './RobotAvatar';

interface MainBotPromptProps {
  onTaskCreated: (task: TaskRecord) => void;
  isSubmitting?: boolean;
}

export const MainBotPrompt: React.FC<MainBotPromptProps> = ({ onTaskCreated, isSubmitting = false }) => {
  const [prompt, setPrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const [botMessage, setBotMessage] = useState<string>('How can I help you today?');
  const [errorNotice, setErrorNotice] = useState<string | null>(null);

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const trimmed = prompt.trim();
    if (!trimmed || loading || isSubmitting) return;

    try {
      setLoading(true);
      setErrorNotice(null);
      setBotMessage(`Working on "${trimmed.length > 30 ? trimmed.slice(0, 30) + '...' : trimmed}"...`);
      const { apiClient } = await import('../services/apiClient');
      // Pass executeImmediately=true so it executes right away
      const newTask = await apiClient.createTask(trimmed, true);
      setPrompt('');
      setBotMessage('Task dispatched successfully!');
      onTaskCreated(newTask);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorNotice(msg);
      setBotMessage('I encountered an issue processing that request.');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="main-bot-card">
      <div className="main-bot-greeting-row">
        <div>
          <h2 className="main-bot-title">
            Good morning, Tulasi <span className="greeting-wave">👋</span>
          </h2>
          <p className="main-bot-subtitle">
            Your AI engineering teammate is ready. What would you like to do today?
          </p>
        </div>

        {/* Floating Cute Robot Assistant Graphic */}
        <div className="main-bot-character-wrap">
          <div className="main-bot-speech-bubble">
            {botMessage}
          </div>
          <div className={`main-bot-avatar-3d ${loading ? 'active-working' : ''}`}>
            <RobotAvatar size={74} />
          </div>
        </div>
      </div>

      {/* Main Large Input Box */}
      <form onSubmit={handleSubmit} className="main-bot-input-box">
        <textarea
          id="main-bot-prompt-input"
          className="main-bot-textarea"
          rows={3}
          placeholder="Ask me to work on a task, open a project, or analyze something..."
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading || isSubmitting}
        />

        <div className="main-bot-toolbar">
          <div className="main-bot-actions-left">
            <button
              type="button"
              className="bot-chip-btn"
              onClick={() => {}}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
              </svg>
              <span>Attach File</span>
            </button>

            <button
              type="button"
              className="bot-chip-btn"
              onClick={() => {}}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"/>
              </svg>
              <span>Use Workspace</span>
            </button>
          </div>

          <button
            type="submit"
            id="main-bot-send-btn"
            className="main-bot-submit-btn"
            disabled={!prompt.trim() || loading || isSubmitting}
            title="Dispatch Task to AI Agent"
          >
            {loading ? (
              <span className="spinner-icon">⏳</span>
            ) : (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13"/>
                <polygon points="22 2 15 22 11 13 2 9 22 2"/>
              </svg>
            )}
          </button>
        </div>
      </form>

      {errorNotice && (
        <div style={{ marginTop: '0.75rem', padding: '0.6rem 0.85rem', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '8px', color: '#b91c1c', fontSize: '0.82rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>⚠️ {errorNotice}</span>
          <button type="button" onClick={() => setErrorNotice(null)} style={{ background: 'none', border: 'none', color: '#991b1b', cursor: 'pointer', fontWeight: 600 }}>✕</button>
        </div>
      )}
    </div>
  );
};
