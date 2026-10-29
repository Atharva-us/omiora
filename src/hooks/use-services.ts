import { useContext } from 'react';
import { ServicesContext, type Services } from '@/services/services-context';

export function useServices(): Services {
  const services = useContext(ServicesContext);
  if (!services) throw new Error('useServices must be used inside <ServicesProvider>.');
  return services;
}
