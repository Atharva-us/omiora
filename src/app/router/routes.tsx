import type { RouteObject } from 'react-router-dom';
import { RouteErrorPage } from '@/app/error-handling/RouteErrorPage';
import { AppLayout } from '@/components/layout/AppLayout';
import { AuthLayout } from '@/components/layout/AuthLayout';
import { MarketingLayout } from '@/components/layout/MarketingLayout';
import { ForgotPasswordPage } from '@/features/authentication/ForgotPasswordPage';
import { RegisterPage } from '@/features/authentication/RegisterPage';
import { SignInPage } from '@/features/authentication/SignInPage';
import { LegalPage } from '@/features/info/LegalPage';
import { NotFoundPage } from '@/features/info/NotFoundPage';
import { StatusPage } from '@/features/info/StatusPage';
import { LandingPage } from '@/features/landing/LandingPage';
import { EditProjectPage } from '@/features/project-creation/EditProjectPage';
import { NewProjectPage } from '@/features/project-creation/NewProjectPage';
import { ProjectsPage } from '@/features/projects/ProjectsPage';

export const routes: RouteObject[] = [
  {
    element: <MarketingLayout />,
    errorElement: <RouteErrorPage />,
    children: [
      { index: true, element: <LandingPage /> },
      { path: 'status', element: <StatusPage /> },
      { path: 'privacy', element: <LegalPage kind="privacy" /> },
      { path: 'terms', element: <LegalPage kind="terms" /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
  {
    element: <AuthLayout />,
    errorElement: <RouteErrorPage />,
    children: [
      { path: 'sign-in', element: <SignInPage /> },
      { path: 'register', element: <RegisterPage /> },
      { path: 'forgot-password', element: <ForgotPasswordPage /> },
    ],
  },
  {
    element: <AppLayout />,
    errorElement: <RouteErrorPage />,
    children: [
      { path: 'projects', element: <ProjectsPage /> },
      {
        path: 'projects/:projectId',
        // The workspace is the heaviest page; loading it on demand keeps the first load small.
        lazy: async () => ({ Component: (await import('@/features/workspace/WorkspacePage')).WorkspacePage }),
      },
      { path: 'projects/:projectId/edit', element: <EditProjectPage /> },
      { path: 'new', element: <NewProjectPage /> },
    ],
  },
];
