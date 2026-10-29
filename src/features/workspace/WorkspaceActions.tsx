import { FileArchive, History, Settings } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/cn';

export type WorkspaceModal = 'history' | 'settings' | 'export';

interface WorkspaceActionsProps {
  onOpen: (modal: WorkspaceModal) => void;
  layout: 'row' | 'column';
}

export function WorkspaceActions({ onOpen, layout }: WorkspaceActionsProps) {
  const column = layout === 'column';
  // `!` is needed because the shared button styles already set justify-center.
  const itemClass = cn(column && 'w-full justify-start!');
  return (
    <div className={cn('flex gap-1', column ? 'flex-col' : 'flex-row flex-wrap')}>
      <Button variant="ghost" size="sm" className={itemClass} onClick={() => onOpen('history')}>
        <History aria-hidden="true" />
        History
      </Button>
      <Button variant="ghost" size="sm" className={itemClass} onClick={() => onOpen('settings')}>
        <Settings aria-hidden="true" />
        Settings
      </Button>
      <Button variant={column ? 'secondary' : 'ghost'} size="sm" className={itemClass} onClick={() => onOpen('export')}>
        <FileArchive aria-hidden="true" />
        Export ZIP
      </Button>
    </div>
  );
}
