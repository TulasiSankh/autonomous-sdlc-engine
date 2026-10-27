import React, { useEffect, useState } from 'react';
import type { TaskRecord } from '../types/api';
import { DeleteConfirmModal } from '../components/DeleteConfirmModal';
import { ErrorBanner } from '../components/ErrorBanner';
import { MainBotPrompt } from '../components/MainBotPrompt';
import { TaskListView } from '../components/TaskListView';
import { RightDashboardWidgets } from '../components/RightDashboardWidgets';
import { apiClient } from '../services/apiClient';

interface DashboardPageProps {
  tasks: TaskRecord[];
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
  onSelectTask: (taskId: string) => void;
  onNavigateNewTask?: () => void;
  onTaskCreated?: (newTask: TaskRecord) => void;
  onTaskDeleted?: (taskId: string) => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({
  tasks,
  loading: _loading,
  error,
  onRefresh,
  onSelectTask,
  onNavigateNewTask,
  onTaskCreated,
  onTaskDeleted,
}) => {
  const [localTasks, setLocalTasks] = useState<TaskRecord[]>(tasks);
  const [taskToDelete, setTaskToDelete] = useState<TaskRecord | null>(null);
  const [isDeletingTask, setIsDeletingTask] = useState<boolean>(false);
  const [deleteTaskError, setDeleteTaskError] = useState<string | null>(null);
  const [isAgentOnline, setIsAgentOnline] = useState<boolean>(true);

  useEffect(() => {
    setLocalTasks(tasks);
  }, [tasks]);

  useEffect(() => {
    const checkAgent = async () => {
      try {
        const res = await apiClient.getLocalAgentStatus();
        setIsAgentOnline(Boolean(res.online));
      } catch {
        setIsAgentOnline(false);
      }
    };
    checkAgent();
  }, []);

  const handleConfirmDelete = async () => {
    if (!taskToDelete) return;
    try {
      setIsDeletingTask(true);
      setDeleteTaskError(null);
      await apiClient.deleteTask(taskToDelete.id);
      setLocalTasks((prev) => prev.filter((t) => t.id !== taskToDelete.id));
      if (onTaskDeleted) {
        onTaskDeleted(taskToDelete.id);
      }
      onRefresh();
      setTaskToDelete(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setDeleteTaskError(msg);
    } finally {
      setIsDeletingTask(false);
    }
  };

  const handleCancelDelete = () => {
    if (!isDeletingTask) {
      setTaskToDelete(null);
      setDeleteTaskError(null);
    }
  };

  return (
    <div className="dashboard-page-wrapper" data-testid="dashboard-page">
      {error && <ErrorBanner message={error} onRetry={onRefresh} />}

      <div className="dashboard-content-columns">
        {/* Left / Main Column: Greeting + Big Bot Input + Task List */}
        <div className="dashboard-main-col">
          <MainBotPrompt
            onTaskCreated={(newTask) => {
              if (onTaskCreated) onTaskCreated(newTask);
              onSelectTask(newTask.id);
            }}
          />

          <TaskListView
            tasks={localTasks}
            onSelectTask={onSelectTask}
            onNavigateNewTask={onNavigateNewTask}
            onDeleteTask={(taskId) => {
              const target = localTasks.find((t) => t.id === taskId);
              if (target) {
                setTaskToDelete(target);
                setDeleteTaskError(null);
              }
            }}
          />
        </div>

        {/* Right Column: System Status + Recent Agent Runs */}
        <div className="dashboard-side-col">
          <RightDashboardWidgets
            tasks={localTasks}
            isAgentOnline={isAgentOnline}
            onSelectTask={onSelectTask}
            onOpenAgentModal={() => {
              const el = document.getElementById('local-agent-status-indicator');
              if (el) el.click();
            }}
          />
        </div>
      </div>

      {/* Task Deletion Confirmation Dialog */}
      <DeleteConfirmModal
        isOpen={taskToDelete !== null}
        taskId={taskToDelete?.id || ''}
        taskTitle={taskToDelete?.task || ''}
        isDeleting={isDeletingTask}
        error={deleteTaskError}
        onConfirm={handleConfirmDelete}
        onCancel={handleCancelDelete}
      />
    </div>
  );
};
