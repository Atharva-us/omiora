import { useState } from 'react';
import { Download, FileArchive } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { Notice } from '@/components/ui/Notice';
import { PROJECT_DEFINITION_FILENAME, projectDefinitionJson } from '@/domain/projects/project-definition';
import { downloadTextFile } from '@/lib/download';
import { slugify } from '@/lib/format';
import type { Project } from '@/domain/projects/project';

interface ExportModalProps {
  project: Project;
  open: boolean;
  onClose: () => void;
}

export function ExportModal({ project, open, onClose }: ExportModalProps) {
  const [downloaded, setDownloaded] = useState(false);

  const close = () => {
    setDownloaded(false);
    onClose();
  };

  return (
    <Modal
      open={open}
      onClose={close}
      title="Export project"
      footer={
        <Button variant="secondary" onClick={close}>
          Close
        </Button>
      }
    >
      <div className="space-y-4">
        <div className="flex gap-3 rounded-lg border border-line bg-elevated/50 p-4 opacity-80">
          <FileArchive aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-faint" />
          <div>
            <p className="text-sm font-medium text-ink">Source code (ZIP)</p>
            <p className="mt-1 text-sm text-muted">
              Unavailable. No source code has been generated for this project, and the packaging service is not
              connected.
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-3 rounded-lg border border-line p-4 sm:flex-row sm:items-center">
          <div className="flex-1">
            <p className="text-sm font-medium text-ink">Project definition (JSON)</p>
            <p className="mt-1 text-sm text-muted">
              Download <span className="font-mono text-xs">{PROJECT_DEFINITION_FILENAME}</span> with your full
              configuration.
            </p>
          </div>
          <Button
            variant="secondary"
            onClick={() => {
              downloadTextFile(
                `${slugify(project.configuration.name)}.${PROJECT_DEFINITION_FILENAME}`,
                projectDefinitionJson(project),
                'application/json',
              );
              setDownloaded(true);
            }}
          >
            <Download aria-hidden="true" />
            Download
          </Button>
        </div>

        {downloaded && (
          <Notice tone="success" role="status">
            The project definition was downloaded.
          </Notice>
        )}
      </div>
    </Modal>
  );
}
