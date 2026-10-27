import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DiffViewer } from '../components/DiffViewer';
import type { FileDiff } from '../types/api';

describe('DiffViewer component', () => {
  const mockDiffs: FileDiff[] = [
    {
      path: 'api/routes/version.py',
      change_type: 'added',
      diff: [
        '--- /dev/null',
        '+++ b/api/routes/version.py',
        '@@ -0,0 +1,8 @@',
        '+from fastapi import APIRouter',
        '+router = APIRouter()',
        '+@router.get("/api/version")',
        '+def get_version():',
        '+    return {"name": "SDLC Engine", "version": "0.1.0"}',
      ].join('\n'),
    },
  ];

  it('renders diff headers, paths, and change type tags', () => {
    render(<DiffViewer diffs={mockDiffs} />);

    expect(screen.getByTestId('diff-viewer')).toBeDefined();
    expect(screen.getByText('api/routes/version.py')).toBeDefined();
    expect(screen.getByText('added')).toBeDefined();
    expect(screen.getByText('+from fastapi import APIRouter')).toBeDefined();
    expect(screen.getByText('--- /dev/null')).toBeDefined();
  });

  it('renders nothing when diffs array is empty', () => {
    const { container } = render(<DiffViewer diffs={[]} />);
    expect(container.firstChild).toBeNull();
  });
});
