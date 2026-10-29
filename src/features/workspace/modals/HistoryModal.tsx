import { History } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { Modal } from '@/components/ui/Modal';
import { formatDateTime } from '@/lib/format';
import type { ProjectHistoryEntry } from '@/domain/projects/project';

interface HistoryModalProps {
  open: boolean;
  onClose: () => void;
  history: ProjectHistoryEntry[];
  isSample: boolean;
}

export function HistoryModal({ open, onClose, history, isSample }: HistoryModalProps) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Project history"
      footer={
        <Button variant="secondary" onClick={onClose}>
          Close
        </Button>
      }
    >
      {history.length === 0 ? (
        <EmptyState icon={History} title="No history yet" className="py-6">
          {isSample ? 'Sample projects have no recorded history.' : 'Changes to this project will be listed here.'}
        </EmptyState>
      ) : (
        <ol className="relative space-y-5 border-l border-line pl-5">
          {history.map((entry) => (
            <li key={entry.id} className="relative">
              <span aria-hidden="true" className="absolute top-1.5 -left-[23.5px] size-2 rounded-full bg-cyan" />
              <p className="text-sm text-ink">{entry.summary}</p>
              <time dateTime={entry.at} className="text-xs text-faint">
                {formatDateTime(entry.at)}
              </time>
            </li>
          ))}
        </ol>
      )}
    </Modal>
  );
}
