import { FlaskConical } from 'lucide-react';
import { EmptyState } from '@/components/ui/EmptyState';

export function TestsPanel() {
  return (
    <EmptyState icon={FlaskConical} title="No test runs" className="h-full">
      Automated testing is not connected yet. When it is, every run and every individual result, including failures,
      will be reported here.
    </EmptyState>
  );
}
