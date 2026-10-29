import { FileJson, FolderOpen } from 'lucide-react';
import { cn } from '@/lib/cn';
import { PROJECT_DEFINITION_FILENAME } from '@/domain/projects/project-definition';

interface FileExplorerProps {
  rootName: string;
  selectedPath: string | null;
  onOpenFile: (path: string) => void;
}

export function FileExplorer({ rootName, selectedPath, onOpenFile }: FileExplorerProps) {
  const selected = selectedPath === PROJECT_DEFINITION_FILENAME;
  return (
    <nav aria-labelledby="explorer-heading">
      <h2 id="explorer-heading" className="px-3 text-[0.6875rem] font-semibold tracking-[0.12em] text-faint uppercase">
        Explorer
      </h2>
      <ul className="mt-2 font-mono text-[0.78125rem]">
        <li>
          <span className="flex items-center gap-1.5 px-3 py-1 text-muted">
            <FolderOpen aria-hidden="true" className="size-3.5 text-azure" />
            {rootName}
          </span>
          <ul>
            <li>
              <button
                type="button"
                onClick={() => onOpenFile(PROJECT_DEFINITION_FILENAME)}
                aria-current={selected ? 'true' : undefined}
                className={cn(
                  'flex w-full items-center gap-1.5 py-1 pr-3 pl-7 text-left transition-colors',
                  selected ? 'bg-cyan/10 text-ink' : 'text-muted hover:bg-elevated hover:text-ink',
                )}
              >
                <FileJson aria-hidden="true" className="size-3.5 text-cyan" />
                {PROJECT_DEFINITION_FILENAME}
              </button>
            </li>
          </ul>
        </li>
      </ul>
      <p className="mt-3 px-3 text-xs leading-relaxed text-faint">
        Generated source files will appear here once code generation is connected.
      </p>
    </nav>
  );
}
