import React, { useState } from 'react';
import { RobotAvatar } from './RobotAvatar';
import { apiClient } from '../services/apiClient';
import type { TaskRecord } from '../types/api';

interface AgentChatInputProps {
  onTaskCreated: (task: TaskRecord) => void;
}

const QUICK_PROMPTS = [
  'Add a GET /api/version endpoint',
  'Implement authentication middleware',
  'Add structured JSON logging with request tracing',
  'Add rate limiting security middleware',
];

export const AgentChatInput: React.FC<AgentChatInputProps> = ({ onTaskCreated }) => {
  const [prompt, setPrompt] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const trimmed = prompt.trim();
    if (!trimmed || isSubmitting) return;

    try {
      setIsSubmitting(true);
      setErrorMessage(null);
      const newTask = await apiClient.createTask(trimmed);
      setPrompt('');
      onTaskCreated(newTask);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMessage(`Agent error: ${msg}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSelectQuickPrompt = (text: string) => {
    setPrompt(text);
  };

  return (
    <div className="agent-chat-wrapper" aria-label="AI Agent Chat Task Bar">
      {/* Quick Prompts Pills */}
      <div className="quick-prompts-bar">
        <span className="quick-prompts-label">⚡ Quick prompts:</span>
        {QUICK_PROMPTS.map((item, idx) => (
          <button
            key={idx}
            type="button"
            className="quick-prompt-pill"
            onClick={() => handleSelectQuickPrompt(item)}
            disabled={isSubmitting}
          >
            {item}
          </button>
        ))}
      </div>

      {/* Main Chat Input Bar */}
      <form
        onSubmit={handleSubmit}
        className={`agent-chat-container ${isSubmitting ? 'submitting' : ''}`}
      >
        <div className="agent-chat-avatar-slot">
          <RobotAvatar size={34} />
        </div>

        <input
          id="agent-chat-input"
          type="text"
          className="agent-chat-input"
          placeholder="Ask your agent to build something..."
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          disabled={isSubmitting}
          aria-label="Ask your agent to build something"
        />

        <button
          id="agent-chat-submit-btn"
          type="submit"
          className="agent-chat-send-btn"
          disabled={!prompt.trim() || isSubmitting}
          aria-label="Send Task to Agent"
          title="Send Task to Agent"
        >
          {isSubmitting ? (
            <span className="spinner-icon" aria-hidden="true">⏳</span>
          ) : (
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          )}
        </button>
      </form>

      {errorMessage && (
        <div className="agent-chat-error" role="alert">
          <span>⚠️ {errorMessage}</span>
          <button
            type="button"
            onClick={() => setErrorMessage(null)}
            className="btn-text-dismiss"
          >
            Dismiss
          </button>
        </div>
      )}
    </div>
  );
};
