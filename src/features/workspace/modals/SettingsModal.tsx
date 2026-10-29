import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { Pencil, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { TextField } from '@/components/ui/Field';
import { Modal } from '@/components/ui/Modal';
import { Notice } from '@/components/ui/Notice';
import type { Project } from '@/domain/projects/project';
import { validateProjectName } from '@/domain/projects/rules';
import { useErrorReporter } from '@/hooks/use-error-reporter';

interface SettingsModalProps {
  project: Project;
  open: boolean;
  onClose: () => void;
  onRename: (name: string) => Promise<void>;
  onDelete: () => Promise<void>;
}

function SettingsForm({ project, onClose, onRename, onDelete }: Omit<SettingsModalProps, 'open'>) {
  const currentName = project.configuration.name;
  const [name, setName] = useState(currentName);
  const [nameError, setNameError] = useState<string | undefined>();
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const readOnly = project.source === 'sample';
  const reportError = useErrorReporter();

  const save = async (event: FormEvent) => {
    event.preventDefault();
    const problem = validateProjectName(name);
    if (problem) return setNameError(problem);
    setSaving(true);
    setActionError(null);
    try {
      await onRename(name.trim());
      setSaved(true);
    } catch (error) {
      setActionError(reportError('project.rename-failed', error, 'The project could not be renamed. Please try again.'));
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    setDeleting(true);
    setActionError(null);
    try {
      await onDelete();
    } catch (error) {
      setActionError(reportError('project.delete-failed', error, 'The project could not be deleted. Please try again.'));
      setDeleting(false);
    }
  };

  if (readOnly) {
    return (
      <Notice tone="warning" title="Sample projects are read-only">
        Settings are available for projects you create.
      </Notice>
    );
  }

  return (
    <div className="space-y-6">
      <form onSubmit={save} noValidate className="space-y-3">
        <TextField
          label="Project name"
          value={name}
          error={nameError}
          onChange={(event) => {
            setName(event.target.value);
            setNameError(undefined);
            setSaved(false);
          }}
        />
        <div className="flex items-center gap-3">
          <Button type="submit" size="sm" loading={saving} disabled={name.trim() === currentName}>
            Save name
          </Button>
          {saved && (
            <span role="status" className="text-sm text-success">
              Saved
            </span>
          )}
        </div>
      </form>

      <div className="border-t border-line-soft pt-5">
        <p className="text-sm font-medium text-ink">Configuration</p>
        <p className="mt-1 text-sm text-muted">Change the platform, stack, or requirements in the setup wizard.</p>
        <Link
          to={`/projects/${project.id}/edit`}
          onClick={onClose}
          className="mt-3 inline-flex items-center gap-2 text-sm text-cyan hover:underline"
        >
          <Pencil aria-hidden="true" className="size-4" />
          Edit configuration
        </Link>
      </div>

      <div className="rounded-lg border border-danger/30 p-4">
        <p className="text-sm font-medium text-ink">Delete project</p>
        <p className="mt-1 text-sm text-muted">
          Permanently removes this project, its notes, and its history from this browser.
        </p>
        {confirmingDelete ? (
          <div className="mt-3 flex flex-wrap gap-2">
            <Button variant="danger" size="sm" onClick={remove} loading={deleting}>
              <Trash2 aria-hidden="true" />
              Yes, delete permanently
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setConfirmingDelete(false)} disabled={deleting}>
              Cancel
            </Button>
          </div>
        ) : (
          <Button variant="danger" size="sm" className="mt-3" onClick={() => setConfirmingDelete(true)}>
            <Trash2 aria-hidden="true" />
            Delete project
          </Button>
        )}
      </div>

      {actionError && (
        <Notice tone="danger" role="alert">
          {actionError}
        </Notice>
      )}
    </div>
  );
}

export function SettingsModal({ open, onClose, ...props }: SettingsModalProps) {
  return (
    <Modal open={open} onClose={onClose} title="Project settings">
      {/* Remounted on each open so the form starts from the saved values. */}
      {open && <SettingsForm onClose={onClose} {...props} />}
    </Modal>
  );
}
