import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DeleteConfirmModal } from '../components/DeleteConfirmModal';

describe('DeleteConfirmModal component', () => {
  it('does not render anything when isOpen is false', () => {
    const { container } = render(
      <DeleteConfirmModal
        isOpen={false}
        taskId="task-123"
        taskTitle="Open my GitHub"
        isDeleting={false}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders modal dialog with task details and preservation notice when isOpen is true', () => {
    render(
      <DeleteConfirmModal
        isOpen={true}
        taskId="task-123"
        taskTitle="Open my GitHub"
        isDeleting={false}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    expect(screen.getByTestId('delete-confirm-modal')).toBeDefined();
    expect(screen.getByText('Delete Task')).toBeDefined();
    expect(screen.getByText('task-123')).toBeDefined();
    expect(screen.getByText('"Open my GitHub"')).toBeDefined();

    // Verifies that local computer files preservation note is shown to user
    expect(
      screen.getByText(/Your local files, folders, and original project directories will never be deleted/i)
    ).toBeDefined();

    // Cancel and Delete buttons exist
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeDefined();
    expect(screen.getByRole('button', { name: '🗑️ Delete Task' })).toBeDefined();
  });

  it('calls onCancel when Cancel button is clicked', () => {
    const handleCancel = vi.fn();
    const handleConfirm = vi.fn();

    render(
      <DeleteConfirmModal
        isOpen={true}
        taskId="task-123"
        taskTitle="Open my GitHub"
        isDeleting={false}
        onConfirm={handleConfirm}
        onCancel={handleCancel}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(handleCancel).toHaveBeenCalledTimes(1);
    expect(handleConfirm).not.toHaveBeenCalled();
  });

  it('calls onConfirm when Delete button is clicked', () => {
    const handleCancel = vi.fn();
    const handleConfirm = vi.fn();

    render(
      <DeleteConfirmModal
        isOpen={true}
        taskId="task-123"
        taskTitle="Open my GitHub"
        isDeleting={false}
        onConfirm={handleConfirm}
        onCancel={handleCancel}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: '🗑️ Delete Task' }));
    expect(handleConfirm).toHaveBeenCalledTimes(1);
    expect(handleCancel).not.toHaveBeenCalled();
  });

  it('disables buttons and shows deleting state while deletion is in progress', () => {
    const handleCancel = vi.fn();
    const handleConfirm = vi.fn();

    render(
      <DeleteConfirmModal
        isOpen={true}
        taskId="task-123"
        taskTitle="Open my GitHub"
        isDeleting={true}
        onConfirm={handleConfirm}
        onCancel={handleCancel}
      />
    );

    const deleteBtn = screen.getByRole('button', { name: 'Deleting...' }) as HTMLButtonElement;
    const cancelBtn = screen.getByRole('button', { name: 'Cancel' }) as HTMLButtonElement;

    expect(deleteBtn.disabled).toBe(true);
    expect(cancelBtn.disabled).toBe(true);

    // Clicking should not trigger handlers while isDeleting
    fireEvent.click(deleteBtn);
    expect(handleConfirm).not.toHaveBeenCalled();
  });

  it('displays error message when error prop is provided', () => {
    render(
      <DeleteConfirmModal
        isOpen={true}
        taskId="task-123"
        taskTitle="Open my GitHub"
        isDeleting={false}
        error="Cannot delete task while execution is in progress. Please cancel first."
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    expect(
      screen.getByText('Cannot delete task while execution is in progress. Please cancel first.')
    ).toBeDefined();
  });
});
