import { MonitorOff } from 'lucide-react';
import { EmptyState } from '@/components/ui/EmptyState';

export function PreviewPanel() {
  return (
    <div className="flex h-full items-center justify-center p-6">
      <div className="w-full max-w-xl rounded-xl border border-dashed border-line bg-obsidian/40">
        <EmptyState icon={MonitorOff} title="No preview available">
          A live preview of the running application appears here after the first successful build. Build execution is
          not connected yet.
        </EmptyState>
      </div>
    </div>
  );
}
