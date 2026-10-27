import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { RobotAvatar } from '../components/RobotAvatar';
import { RobotIllustration } from '../components/RobotIllustration';
import { AgentActivityPanel } from '../components/AgentActivityPanel';
import { AgentChatInput } from '../components/AgentChatInput';
import { Header } from '../components/Header';
import type { TaskRecord } from '../types/api';

describe('Orbit AI New Agent Components', () => {
  const mockTask: TaskRecord = {
    id: 'task-test-1234',
    task: 'Add a GET /api/version endpoint',
    status: 'planned',
    plan: {
      task: 'Add a GET /api/version endpoint',
      summary: 'Structured plan for version route',
      steps: ['Step 1: Create version router', 'Step 2: Mount to FastAPI'],
      files_to_inspect: ['api/main.py'],
      acceptance_criteria: ['Returns app name and version'],
      tests_to_run: ['pytest tests/test_version.py'],
      risks: ['None'],
    },
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    revision_count: 0,
  };

  it('renders RobotAvatar and RobotIllustration correctly', () => {
    const { container: avatarContainer } = render(<RobotAvatar size={48} />);
    expect(avatarContainer.querySelector('svg')).toBeDefined();

    const { container: illustrationContainer } = render(<RobotIllustration />);
    expect(illustrationContainer.querySelector('svg')).toBeDefined();
    expect(screen.getByLabelText('Orbit AI Robot Assistant')).toBeDefined();
  });

  it('renders Header with Orbit AI branding and navigation', () => {
    render(<Header activeView="dashboard" onNavigate={vi.fn()} />);
    expect(screen.getByText('Orbit AI')).toBeDefined();
    expect(screen.getByText('Your Autonomous Engineering Teammate')).toBeDefined();
    expect(screen.getByText('Dashboard')).toBeDefined();
    expect(screen.getByText('Tasks')).toBeDefined();
    expect(screen.getByText('Agent Runs')).toBeDefined();
    expect(screen.getByText('Workspaces')).toBeDefined();
    expect(screen.getByText('Settings')).toBeDefined();
  });

  it('renders AgentActivityPanel with real lifecycle stages', () => {
    render(<AgentActivityPanel tasks={[mockTask]} />);
    expect(screen.getByTestId('agent-activity-panel')).toBeDefined();
    expect(screen.getByText('AI Agent Activity Timeline')).toBeDefined();
    expect(screen.getByText('Analyzing Task Requirements')).toBeDefined();
    expect(screen.getByText('Generating Implementation Plan')).toBeDefined();
    expect(screen.getByText('Creating Code Proposal')).toBeDefined();
    expect(screen.getByText('Applying Changes to Isolated Workspace')).toBeDefined();
    expect(screen.getByText('Running Tests & Verification')).toBeDefined();
    expect(screen.getByText('task-test-1234')).toBeDefined();
  });

  it('renders AgentChatInput with placeholder and quick prompt pills', () => {
    const handleCreated = vi.fn();
    render(<AgentChatInput onTaskCreated={handleCreated} />);

    const input = screen.getByPlaceholderText('Ask your agent to build something...');
    expect(input).toBeDefined();

    // Quick prompt pills
    const pill = screen.getByText('Add a GET /api/version endpoint');
    expect(pill).toBeDefined();
    fireEvent.click(pill);
    expect((input as HTMLInputElement).value).toBe('Add a GET /api/version endpoint');
  });
});
