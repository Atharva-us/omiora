import { useCallback } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, FileQuestion } from 'lucide-react';
import { ButtonLink } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { Notice } from '@/components/ui/Notice';
import { LoadingBlock } from '@/components/ui/Spinner';
import { useAsyncData } from '@/hooks/use-async-data';
import { useServices } from '@/hooks/use-services';
import { ProjectWizard } from './ProjectWizard';
import { draftFromConfiguration, WIZARD_STEPS } from './wizard-model';

export function EditProjectPage() {
  const { projectId = '' } = useParams();
  const navigate = useNavigate();
  const { projects } = useServices();
  const loadProject = useCallback(() => projects.getProject(projectId), [projects, projectId]);
  const { data: project, errorMessage, isLoading } = useAsyncData(loadProject, 'project-edit.load-failed');

  const backTo = `/projects/${projectId}`;

  let content;
  if (isLoading && !project) {
    content = <LoadingBlock label="Loading project" />;
  } else if (errorMessage) {
    content = (
      <Notice tone="danger" role="alert" title="The project could not be loaded">
        {errorMessage}
      </Notice>
    );
  } else if (!project) {
    content = (
      <EmptyState
        icon={FileQuestion}
        title="Project not found"
        action={<ButtonLink to="/projects">Back to projects</ButtonLink>}
      >
        It may have been deleted, or it was created in a different browser.
      </EmptyState>
    );
  } else if (project.source === 'sample') {
    content = (
      <Notice tone="warning" title="Sample projects are read-only">
        Sample projects demonstrate the interface and cannot be edited.{' '}
        <Link to="/new" className="text-ink underline underline-offset-4">
          Create your own project
        </Link>{' '}
        to configure one.
      </Notice>
    );
  } else {
    content = (
      <ProjectWizard
        mode="edit"
        initialState={{ step: WIZARD_STEPS.length - 1, configuration: draftFromConfiguration(project.configuration) }}
        onComplete={async (configuration) => {
          await projects.updateProject(project.id, { name: configuration.name, configuration });
          navigate(backTo);
        }}
      />
    );
  }

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
      <Link to={backTo} className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink">
        <ArrowLeft aria-hidden="true" className="size-4" />
        Back to workspace
      </Link>
      <h1 className="mt-4 mb-10 text-3xl font-semibold tracking-[-0.025em]">
        Edit configuration{project ? <span className="text-muted">: {project.configuration.name}</span> : null}
      </h1>
      {content}
    </div>
  );
}
