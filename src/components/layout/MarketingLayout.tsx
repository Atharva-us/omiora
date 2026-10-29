import { Outlet } from 'react-router-dom';
import { Footer } from '@/components/navigation/Footer';
import { Navbar } from '@/components/navigation/Navbar';
import { useScrollToHash } from '@/hooks/use-scroll-to-hash';
import { SkipLink } from './SkipLink';

export function MarketingLayout() {
  useScrollToHash();
  return (
    <div className="flex min-h-dvh flex-col">
      <SkipLink />
      <Navbar />
      <main id="main" className="flex-1">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}
