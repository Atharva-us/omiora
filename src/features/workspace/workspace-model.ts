import { ClipboardCheck, Code2, FlaskConical, ListChecks, ListTodo, Monitor, ScrollText } from 'lucide-react';
import type { TabItem } from '@/components/ui/Tabs';
import { requirementLabel, technologyNames } from '@/domain/projects/catalog';
import type { ProjectConfiguration } from '@/domain/projects/project';

export type WorkspaceTab = 'preview' | 'requirements' | 'plan' | 'code' | 'tasks' | 'tests' | 'logs';

export const WORKSPACE_TABS: readonly TabItem<WorkspaceTab>[] = [
  { id: 'preview', label: 'Preview', icon: Monitor },
  { id: 'requirements', label: 'Requirements', icon: ListTodo },
  { id: 'plan', label: 'Plan', icon: ClipboardCheck },
  { id: 'code', label: 'Code', icon: Code2 },
  { id: 'tasks', label: 'Tasks', icon: ListChecks },
  { id: 'tests', label: 'Tests', icon: FlaskConical },
  { id: 'logs', label: 'Logs', icon: ScrollText },
];

export interface ChecklistItem {
  id: string;
  label: string;
  group: 'Platform and stack' | 'Core features' | 'Additional requirements';
}

/**
 * Converts the saved configuration into a checklist. This is a direct,
 * deterministic restatement of the user's answers, not an AI-generated plan.
 */
export function configurationChecklist(configuration: ProjectConfiguration): ChecklistItem[] {
  const items: ChecklistItem[] = [];
  const { stack, requirements } = configuration;

  items.push({
    id: 'stack',
    group: 'Platform and stack',
    label:
      stack.mode === 'recommend'
        ? 'Recommend a technology stack'
        : `Use ${technologyNames(stack.technologies).join(', ')}`,
  });
  if (configuration.referenceUrl) {
    items.push({ id: 'reference', group: 'Platform and stack', label: `Follow design reference ${configuration.referenceUrl}` });
  }

  requirements.features.forEach((feature) =>
    items.push({ id: `feature-${feature}`, group: 'Core features', label: requirementLabel(feature) }),
  );

  requirements.custom
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .forEach((line, index) => items.push({ id: `custom-${index}`, group: 'Additional requirements', label: line }));

  return items;
}
