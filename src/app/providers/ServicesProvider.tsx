import type { ReactNode } from 'react';
import { ServicesContext, type Services } from '@/services/services-context';

interface ServicesProviderProps {
  children: ReactNode;
  /** Built by the composition root (`createServices`) or by tests. */
  services: Services;
}

export function ServicesProvider({ children, services }: ServicesProviderProps) {
  return <ServicesContext.Provider value={services}>{children}</ServicesContext.Provider>;
}
