import { useCallback, useState } from 'react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import type { RequirementsVersion, VersionSummary } from '@/domain/requirements/requirements';
import { useAsyncData } from '@/hooks/use-async-data';
import { useServices } from '@/hooks/use-services';
import { Section } from './RequirementsDocumentView';

const FIELD_LABELS: Record<string, string> = {
  statement: 'statement',
  kind: 'kind',
  priority: 'priority',
  confidence: 'confidence',
  source: 'source',
  evidence: 'evidence',
  acceptance_criteria: 'acceptance criteria',
  tags: 'tags',
};

function DiffView({ version }: { version: RequirementsVersion }) {
  const diff = version.diff;
  if (!diff) return null;
  const empty = !diff.added.length && !diff.deprecated.length && !diff.changed.length && !diff.contextFields.length;
  return (
    <div aria-label={`Changes in v${version.version}`} className="mt-2 rounded-md border border-line-soft p-3 text-[0.8125rem] text-muted">
      <p className="text-xs text-faint">
        v{diff.fromVersion} → v{version.version}
      </p>
      {empty && <p>No requirement changes.</p>}
      {diff.added.length > 0 && <p>Added: {diff.added.join(', ')}</p>}
      {diff.deprecated.length > 0 && <p>Deprecated: {diff.deprecated.join(', ')}</p>}
      {diff.changed.map((change) => (
        <p key={change.id}>
          Changed {change.id}: {change.fields.map((field) => FIELD_LABELS[field] ?? field).join(', ')}
        </p>
      ))}
      {diff.contextFields.length > 0 && <p>Context updated: {diff.contextFields.join(', ')}</p>}
    </div>
  );
}

/** Every version of the session, with what changed between consecutive versions. Render it with
 * `key={currentVersion}` so a new version reloads the list. */
export function VersionHistory({ sessionId }: { sessionId: string }) {
  const { requirements } = useServices();
  const [open, setOpen] = useState<number | null>(null);
  const loadVersions = useCallback(() => requirements.listVersions(sessionId), [requirements, sessionId]);
  const { data: versions } = useAsyncData(loadVersions, 'requirements.versions-failed');
  const loadDiff = useCallback(
    async () => (open && open > 1 ? requirements.getVersion(sessionId, open, open - 1) : null),
    [requirements, sessionId, open],
  );
  const { data: diffVersion } = useAsyncData(loadDiff, 'requirements.diff-failed');

  if (!versions || versions.length === 0) return null;
  return (
    <Section title="Version history">
      <ol className="divide-y divide-line-soft rounded-lg border border-line bg-surface text-sm">
        {[...versions].reverse().map((summary: VersionSummary) => (
          <li key={summary.id} className="px-4 py-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-xs text-ink">v{summary.version}</span>
              <span className="text-xs text-faint">
                {summary.requirementCount} requirements · {summary.mustCount} must
              </span>
              {summary.ready && <Badge>ready</Badge>}
              {summary.frozenAt && <Badge tone="warning">frozen</Badge>}
              {summary.approvedAt && <Badge tone="success">approved</Badge>}
              <span className="flex-1" />
              {summary.version > 1 && (
                <Button size="sm" variant="ghost" onClick={() => setOpen(open === summary.version ? null : summary.version)}>
                  {open === summary.version ? 'Hide changes' : 'Show changes'}
                </Button>
              )}
            </div>
            {open === summary.version && diffVersion?.version === summary.version && <DiffView version={diffVersion} />}
          </li>
        ))}
      </ol>
    </Section>
  );
}
