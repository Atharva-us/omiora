import { useId, useState, type FormEvent, type KeyboardEvent } from 'react';
import { Info, SendHorizontal } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Notice } from '@/components/ui/Notice';
import { PLATFORM_LABELS } from '@/domain/projects/catalog';
import type { Project, ProjectNote } from '@/domain/projects/project';
import { PROJECT_LIMITS, validateNoteContent } from '@/domain/projects/rules';
import { useErrorReporter } from '@/hooks/use-error-reporter';
import { formatDateTime } from '@/lib/format';

interface ChatPanelProps {
  project: Project;
  notes: ProjectNote[];
  readOnly: boolean;
  onAddNote: (content: string) => Promise<void>;
}

export function ChatPanel({ project, notes, readOnly, onAddNote }: ChatPanelProps) {
  const [draft, setDraft] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const inputId = useId();
  const reportError = useErrorReporter();

  const submit = async () => {
    const problem = validateNoteContent(draft);
    if (problem) {
      setError(problem);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await onAddNote(draft.trim());
      setDraft('');
    } catch (cause) {
      setError(reportError('notes.add-failed', cause, 'The note could not be saved. Please try again.'));
    } finally {
      setSaving(false);
    }
  };

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    void submit();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      void submit();
    }
  };

  return (
    <section aria-labelledby="chat-heading" className="flex min-h-0 flex-1 flex-col">
      <div className="flex h-12 shrink-0 items-center justify-between border-b border-line-soft px-4">
        <h2 id="chat-heading" className="text-sm font-semibold text-ink">
          Chat and requirements
        </h2>
      </div>

      <div className="scrollbar-thin min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
        <div className="rounded-lg border border-line bg-elevated/60 p-3.5">
          <p className="text-[0.6875rem] font-semibold tracking-[0.12em] text-faint uppercase">Project brief</p>
          <p className="mt-2 text-sm leading-relaxed whitespace-pre-line text-ink">{project.configuration.description}</p>
          <p className="mt-2 text-xs text-faint">{PLATFORM_LABELS[project.configuration.platform]}</p>
        </div>

        <div className="flex gap-2.5 rounded-lg border border-line-soft p-3 text-[0.8125rem] leading-relaxed text-muted">
          <Info aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-azure" />
          <p>
            The AI assistant is not connected yet, so there are no replies. Notes you add here are saved to this
            project&apos;s requirements and will be handed to the engine when it is available.
          </p>
        </div>

        {notes.length > 0 && (
          <ol aria-label="Requirement notes" className="space-y-3">
            {notes.map((note) => (
              <li key={note.id} className="rounded-lg border border-line bg-surface p-3">
                <p className="text-sm leading-relaxed whitespace-pre-line text-ink">{note.content}</p>
                <p className="mt-2 text-xs text-faint">
                  Note · <time dateTime={note.at}>{formatDateTime(note.at)}</time>
                </p>
              </li>
            ))}
          </ol>
        )}
      </div>

      <div className="shrink-0 border-t border-line-soft p-3">
        {readOnly ? (
          <Notice tone="warning">Sample projects are read-only. Create your own project to add notes.</Notice>
        ) : (
          <form onSubmit={onSubmit} noValidate>
            <label htmlFor={inputId} className="sr-only">
              Add a requirement note
            </label>
            <div className="rounded-lg border border-line bg-surface focus-within:border-cyan/60">
              <textarea
                id={inputId}
                value={draft}
                rows={3}
                onChange={(event) => {
                  setDraft(event.target.value);
                  if (error) setError(null);
                }}
                onKeyDown={onKeyDown}
                placeholder="Add a requirement, constraint, or clarification…"
                aria-invalid={error ? true : undefined}
                aria-describedby={error ? `${inputId}-error` : undefined}
                className="block w-full resize-none rounded-t-lg bg-transparent px-3 pt-2.5 text-sm text-ink placeholder:text-faint focus:outline-none"
              />
              <div className="flex items-center justify-between px-2 pb-2">
                <span className="pl-1 font-mono text-xs text-faint">
                  {draft.length}/{PROJECT_LIMITS.noteMax}
                </span>
                <Button type="submit" size="sm" loading={saving}>
                  {!saving && <SendHorizontal aria-hidden="true" />}
                  Add note
                </Button>
              </div>
            </div>
            {error && (
              <p id={`${inputId}-error`} role="alert" className="mt-2 text-[0.8125rem] text-danger">
                {error}
              </p>
            )}
          </form>
        )}
      </div>
    </section>
  );
}
