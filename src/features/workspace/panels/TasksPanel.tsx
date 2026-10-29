import { Circle } from 'lucide-react';
import { Notice } from '@/components/ui/Notice';
import type { ProjectConfiguration } from '@/domain/projects/project';
import { configurationChecklist, type ChecklistItem } from '../workspace-model';

export function TasksPanel({ configuration }: { configuration: ProjectConfiguration }) {
  const items = configurationChecklist(configuration);
  const groups = items.reduce<Map<ChecklistItem['group'], ChecklistItem[]>>((map, item) => {
    map.set(item.group, [...(map.get(item.group) ?? []), item]);
    return map;
  }, new Map());

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-5 sm:p-6">
      <Notice tone="info" title="Requirements checklist">
        This list restates your configuration. AI planning is not connected, so it is not an engineering plan and no
        work has started on any item.
      </Notice>

      {[...groups.entries()].map(([group, groupItems]) => (
        <section key={group} aria-label={group}>
          <h3 className="text-[0.6875rem] font-semibold tracking-[0.12em] text-faint uppercase">{group}</h3>
          <ul className="mt-2 divide-y divide-line-soft rounded-lg border border-line bg-surface">
            {groupItems.map((item) => (
              <li key={item.id} className="flex items-center gap-3 px-4 py-3">
                <Circle aria-hidden="true" className="size-4 shrink-0 text-faint" />
                <span className="min-w-0 flex-1 text-sm break-words text-ink">{item.label}</span>
                <span className="shrink-0 text-xs text-faint">Not started</span>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
