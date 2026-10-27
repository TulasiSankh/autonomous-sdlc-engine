import { useEffect, useState } from 'react';
import type { TaskRecord } from './types/api';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { DashboardPage } from './pages/DashboardPage';
import { NewTaskPage } from './pages/NewTaskPage';
import { TaskDetailsPage } from './pages/TaskDetailsPage';
import { apiClient } from './services/apiClient';

export function App() {
  const [activeView, setActiveView] = useState<'dashboard' | 'new-task' | 'task-details'>('dashboard');
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [tasks, setTasks] = useState<TaskRecord[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isAgentOnline, setIsAgentOnline] = useState<boolean>(true);

  // Load all tasks from SQLite backend
  const loadTasks = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await apiClient.listTasks();
      // Sort tasks newest first
      const sorted = [...data].sort((a, b) => {
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      });
      setTasks(sorted);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const checkAgentStatus = async () => {
    try {
      const res = await apiClient.getLocalAgentStatus();
      setIsAgentOnline(Boolean(res.online));
    } catch {
      setIsAgentOnline(false);
    }
  };

  // Sync with URL hash for navigation preservation
  useEffect(() => {
    loadTasks();
    checkAgentStatus();

    const handleHashChange = () => {
      const hash = window.location.hash;
      if (hash.startsWith('#/task/')) {
        const id = hash.replace('#/task/', '').trim();
        if (id) {
          setSelectedTaskId(id);
          setActiveView('task-details');
        }
      } else if (hash === '#/new') {
        setActiveView('new-task');
      } else {
        setActiveView('dashboard');
      }
    };

    handleHashChange();
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const handleSelectTask = (taskId: string) => {
    setSelectedTaskId(taskId);
    setActiveView('task-details');
    window.location.hash = `#/task/${taskId}`;
  };

  const handleNavigate = (view: 'dashboard' | 'new-task') => {
    setActiveView(view);
    if (view === 'dashboard') {
      window.location.hash = '#/';
      loadTasks();
    } else {
      window.location.hash = '#/new';
    }
  };

  const handleSidebarNavigate = (nav: string) => {
    if (nav === 'dashboard' || nav === 'tasks' || nav === 'agent-runs' || nav === 'workspaces' || nav === 'settings') {
      handleNavigate('dashboard');
    }
  };

  const handleTaskCreated = (newTask: TaskRecord) => {
    setTasks((prev) => [newTask, ...prev]);
    setSelectedTaskId(newTask.id);
    setActiveView('task-details');
    window.location.hash = `#/task/${newTask.id}`;
  };

  const handleTaskDeleted = (deletedTaskId: string) => {
    setTasks((prev) => prev.filter((t) => t.id !== deletedTaskId));
    if (selectedTaskId === deletedTaskId) {
      setSelectedTaskId(null);
      setActiveView('dashboard');
      window.location.hash = '#/';
    }
  };

  const handleRefreshSingleTask = async (taskId: string): Promise<TaskRecord> => {
    const updated = await apiClient.getTask(taskId);
    setTasks((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
    return updated;
  };

  const selectedTask = tasks.find((t) => t.id === selectedTaskId);

  return (
    <div className="app-layout-root">
      <Header activeView={activeView} onNavigate={handleNavigate} />
      <div className="app-body-container">
        <Sidebar
          activeNav={activeView === 'dashboard' ? 'dashboard' : ''}
          onNavigate={handleSidebarNavigate}
          tasksCount={tasks.length}
          isAgentOnline={isAgentOnline}
          onOpenAgentModal={() => {
            const el = document.getElementById('local-agent-status-indicator');
            if (el) el.click();
          }}
        />
        <main className="main-content-area">
          {activeView === 'dashboard' && (
            <DashboardPage
              tasks={tasks}
              loading={loading}
              error={error}
              onRefresh={loadTasks}
              onSelectTask={handleSelectTask}
              onNavigateNewTask={() => handleNavigate('new-task')}
              onTaskCreated={handleTaskCreated}
              onTaskDeleted={handleTaskDeleted}
            />
          )}

          {activeView === 'new-task' && (
            <NewTaskPage
              onTaskCreated={handleTaskCreated}
              onCancel={() => handleNavigate('dashboard')}
            />
          )}

          {activeView === 'task-details' && (
            selectedTask ? (
              <TaskDetailsPage
                task={selectedTask}
                onBack={() => handleNavigate('dashboard')}
                onRefreshTask={handleRefreshSingleTask}
                onTaskDeleted={handleTaskDeleted}
              />
            ) : (
              <div className="container" style={{ textAlign: 'center', padding: '4rem 1rem' }}>
                <h2>Task Not Found</h2>
                <p style={{ marginTop: '0.5rem', marginBottom: '1.5rem' }}>
                  The requested task '{selectedTaskId}' could not be located in the task index.
                </p>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => handleNavigate('dashboard')}
                >
                  ← Return to Dashboard
                </button>
              </div>
            )
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
