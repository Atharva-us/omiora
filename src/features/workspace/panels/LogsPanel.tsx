import { ScrollText } from 'lucide-react';
import { EmptyState } from '@/components/ui/EmptyState';
import type { ProjectHistoryEntry } from '@/domain/projects/project';
import { formatLogTimestamp } from '@/lib/format';

export function LogsPanel({ history, isSample }: { history: ProjectHistoryEntry[]; isSample: boolean }) {
  const entries = [...history].sort((a, b) => a.at.localeCompare(b.at));
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex h-10 shrink-0 items-center border-b border-line-soft px-4 text-xs text-faint">
        System events for this project. Build and sandbox logs will stream here once build execution is connected.
      </div>
      {entries.length === 0 ? (
        <EmptyState icon={ScrollText} title="No log entries" className="flex-1">
          {isSample ? 'Sample projects have no recorded events.' : 'Events will appear as you work on this project.'}
        </EmptyState>
      ) : (
        <ol aria-label="Project log" className="scrollbar-thin min-h-0 flex-1 overflow-auto bg-obsidian/50 py-3 font-mono text-[0.78125rem] leading-6">
          {entries.map((entry) => (
            <li key={entry.id} className="flex gap-4 px-4">
              <time dateTime={entry.at} className="shrink-0 text-faint">
                {formatLogTimestamp(entry.at)}
              </time>
              <span className="shrink-0 text-azure">system</span>
              <span className="min-w-0 text-muted">{entry.summary}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
