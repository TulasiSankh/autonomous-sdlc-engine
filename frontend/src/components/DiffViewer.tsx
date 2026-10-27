import React, { useState } from 'react';
import type { FileDiff } from '../types/api';

interface DiffViewerProps {
  diffs: FileDiff[];
  title?: string;
}

export const DiffViewer: React.FC<DiffViewerProps> = ({
  diffs,
  title = 'Unified Diffs (Isolated Workspace)',
}) => {
  const [copiedPath, setCopiedPath] = useState<string | null>(null);

  const copyDiff = (path: string, diffText: string) => {
    navigator.clipboard?.writeText(diffText);
    setCopiedPath(path);
    setTimeout(() => setCopiedPath(null), 2000);
  };

  if (!diffs || diffs.length === 0) {
    return null;
  }

  return (
    <div className="card diff-viewer-card" data-testid="diff-viewer">
      <div className="diff-viewer-header">
        <div className="diff-title-group">
          <span className="diff-title-icon">📄</span>
          <h4 className="diff-title-text">
            {title} ({diffs.length} file{diffs.length === 1 ? '' : 's'})
          </h4>
        </div>
        <div className="diff-meta-tag">
          <span className="security-dot" />
          <span>confinement: isolated sandbox</span>
        </div>
      </div>

      <div className="diff-files-list">
        {diffs.map((fileDiff, idx) => {
          const lines = fileDiff.diff.split('\n');

          return (
            <div key={idx} className="diff-file-block">
              {/* File Header */}
              <div className="diff-file-header">
                <div className="diff-file-path-group">
                  <span className="diff-file-icon">📁</span>
                  <span className="diff-file-path">{fileDiff.path}</span>
                  <span
                    className={`diff-change-badge ${fileDiff.change_type}`}
                  >
                    {fileDiff.change_type}
                  </span>
                </div>

                <button
                  type="button"
                  className="btn btn-secondary btn-xs"
                  onClick={() => copyDiff(fileDiff.path, fileDiff.diff)}
                  title="Copy unified diff patch to clipboard"
                >
                  {copiedPath === fileDiff.path ? '✓ Copied' : '📋 Copy Diff'}
                </button>
              </div>

              {/* Diff Code Body */}
              <div className="diff-code-container">
                <pre className="diff-code-pre">
                  {lines.map((line, lineIdx) => {
                    let lineClassName = 'diff-line normal';

                    if (line.startsWith('+') && !line.startsWith('+++')) {
                      lineClassName = 'diff-line addition';
                    } else if (line.startsWith('-') && !line.startsWith('---')) {
                      lineClassName = 'diff-line deletion';
                    } else if (line.startsWith('@@')) {
                      lineClassName = 'diff-line chunk-header';
                    } else if (line.startsWith('---') || line.startsWith('+++')) {
                      lineClassName = 'diff-line file-boundary';
                    }

                    return (
                      <span key={lineIdx} className={lineClassName}>
                        {line || ' '}
                      </span>
                    );
                  })}
                </pre>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
