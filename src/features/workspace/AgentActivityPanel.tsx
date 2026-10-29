import { Link } from 'react-router-dom';
import { Bot } from 'lucide-react';
import { AGENT_ROLES, type AgentRole } from '@/domain/engineering/types';
import { formatLogTimestamp } from '@/lib/format';
import { AGENT_LABELS, describeRunEvent } from './run/run-model';
import type { ProjectRun } from './run/use-project-run';

// Keyed by role so a new planned agent cannot be added without a description.
const RESPONSIBILITIES: Record<AgentRole, string> = {
  'project-manager': 'Plans work and coordinates the other agents',
  'requirements-analyst': 'Turns the brief into testable requirements',
  'reference-design': 'Analyses references and defines the UI',
  'software-architect': 'Chooses structure, stack, and contracts',
  'frontend-engineer': 'Builds the web client',
  'backend-engineer': 'Builds APIs, services, and integrations',
  'mobile-engineer': 'Builds the iOS and Android apps',
  'database-engineer': 'Designs schemas and migrations',
  'qa-debugging': 'Writes and runs tests, diagnoses failures',
  'security-release': 'Reviews security and prepares releases',
};

export function AgentActivityPanel({ run }: { run: ProjectRun }) {
  const recent = run.events.slice(-12).reverse();
  return (
    <section aria-labelledby="agents-heading" className="flex min-h-0 flex-1 flex-col">
      <div className="flex h-12 shrink-0 items-center border-b border-line-soft px-4">
        <h2 id="agents-heading" className="text-sm font-semibold text-ink">
          Agent activity
        </h2>
      </div>
      <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto p-4">
        {recent.length === 0 ? (
          <div className="rounded-lg border border-dashed border-line px-4 py-6 text-center">
            <Bot aria-hidden="true" className="mx-auto size-5 text-faint" />
            <p className="mt-2 text-sm font-medium text-ink">No agent activity</p>
            <p className="mt-1 text-xs leading-relaxed text-muted">
              {run.available
                ? 'Planning activity recorded by the server appears here. Start with the Requirements tab.'
                : 'Agent runs need API mode. Nothing is simulated here.'}
            </p>
          </div>
        ) : (
          <ol aria-label="Recorded run events" className="space-y-2">
            {recent.map((event) => (
              <li key={event.seq} className="text-xs">
                <p className="text-ink">{describeRunEvent(event)}</p>
                <time dateTime={event.at} className="font-mono text-faint">
                  #{event.seq} · {formatLogTimestamp(event.at)}
                </time>
              </li>
            ))}
          </ol>
        )}

        <h3 className="mt-6 text-[0.6875rem] font-semibold tracking-[0.12em] text-faint uppercase">Agents</h3>
        <ul className="mt-2 space-y-1">
          {AGENT_ROLES.map((role) => {
            const live = (role === 'project-manager' || role === 'requirements-analyst') && run.available;
            return (
              <li key={role} className="flex items-center gap-3 rounded-md px-2 py-2">
                <span aria-hidden="true" className={`size-1.5 shrink-0 rounded-full ${live ? 'bg-success' : 'bg-line'}`} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-ink">{AGENT_LABELS[role]}</p>
                  <p className="truncate text-xs text-faint">{RESPONSIBILITIES[role]}</p>
                </div>
                <span className="text-xs text-faint">{live ? 'Available' : 'Planned'}</span>
              </li>
            );
          })}
        </ul>
        <Link to="/status" className="mt-4 inline-block text-xs text-muted underline-offset-4 hover:text-ink hover:underline">
          View platform status
        </Link>
      </div>
    </section>
  );
}
