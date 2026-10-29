import { useEffect, useState } from 'react';
import { Check, Copy, FileCode2 } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';

interface CodePanelProps {
  path: string | null;
  contents: string | null;
  onOpenDefinition: () => void;
}

export function CodePanel({ path, contents, onOpenDefinition }: CodePanelProps) {
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'failed'>('idle');

  useEffect(() => {
    if (copyState === 'idle') return;
    const timer = window.setTimeout(() => setCopyState('idle'), 2000);
    return () => window.clearTimeout(timer);
  }, [copyState]);

  if (!path || contents === null) {
    return (
      <EmptyState
        icon={FileCode2}
        title="No file open"
        className="h-full"
        action={
          <Button variant="secondary" size="sm" onClick={onOpenDefinition}>
            Open project definition
          </Button>
        }
      >
        Select a file in the explorer. The code editor is not connected yet; files open read-only.
      </EmptyState>
    );
  }

  const lines = contents.replace(/\n$/, '').split('\n');

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(contents);
      setCopyState('copied');
    } catch {
      setCopyState('failed');
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex h-10 shrink-0 items-center justify-between gap-3 border-b border-line-soft px-4">
        <div className="flex min-w-0 items-center gap-2">
          <span className="truncate font-mono text-xs text-ink">{path}</span>
          <Badge>Read-only</Badge>
        </div>
        <Button variant="ghost" size="sm" onClick={copy} aria-live="polite">
          {copyState === 'copied' ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
          {copyState === 'copied' ? 'Copied' : copyState === 'failed' ? 'Copy failed' : 'Copy'}
        </Button>
      </div>
      <div className="scrollbar-thin min-h-0 flex-1 overflow-auto bg-obsidian/50">
        <pre className="py-3 font-mono text-[0.8125rem] leading-6">
          <code>
            {lines.map((line, index) => (
              <span key={index} className="flex">
                <span aria-hidden="true" className="w-12 shrink-0 pr-4 text-right text-faint/70 select-none">
                  {index + 1}
                </span>
                <span className="pr-6 whitespace-pre text-muted">{line}</span>
              </span>
            ))}
          </code>
        </pre>
      </div>
      <p className="shrink-0 border-t border-line-soft px-4 py-2 text-xs text-faint">
        Editing is not available yet. This file is derived from your saved configuration.
      </p>
    </div>
  );
}
