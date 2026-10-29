import { useCallback, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { FileQuestion, FolderTree, LayoutPanelLeft, MessageSquare } from 'lucide-react';
import { LoadErrorNotice } from '@/components/feedback/LoadErrorNotice';
import { ButtonLink } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { Notice } from '@/components/ui/Notice';
import { LoadingBlock } from '@/components/ui/Spinner';
import { TabPanel, Tabs } from '@/components/ui/Tabs';
import { useAsyncData } from '@/hooks/use-async-data';
import { useServices } from '@/hooks/use-services';
import { cn } from '@/lib/cn';
import { slugify } from '@/lib/format';
import { PROJECT_DEFINITION_FILENAME, projectDefinitionJson } from '@/domain/projects/project-definition';
import { AgentActivityPanel } from './AgentActivityPanel';
import { ChatPanel } from './ChatPanel';
import { FileExplorer } from './FileExplorer';
import { ExportModal } from './modals/ExportModal';
import { HistoryModal } from './modals/HistoryModal';
import { SettingsModal } from './modals/SettingsModal';
import { CodePanel } from './panels/CodePanel';
import { LogsPanel } from './panels/LogsPanel';
import { PlanPanel } from './panels/PlanPanel';
import { PreviewPanel } from './panels/PreviewPanel';
import { TasksPanel } from './panels/TasksPanel';
import { TestsPanel } from './panels/TestsPanel';
import { ProjectSummary } from './ProjectSummary';
import { RequirementsPanel } from './requirements/RequirementsPanel';
import { useRequirementsSession } from './requirements/use-requirements-session';
import { useProjectRun } from './run/use-project-run';
import { WorkspaceActions, type WorkspaceModal } from './WorkspaceActions';
import { WORKSPACE_TABS, type WorkspaceTab } from './workspace-model';

type MobileView = 'chat' | 'workspace' | 'files';

const MOBILE_VIEWS: { id: MobileView; label: string; icon: typeof MessageSquare }[] = [
  { id: 'chat', label: 'Chat', icon: MessageSquare },
  { id: 'workspace', label: 'Workspace', icon: LayoutPanelLeft },
  { id: 'files', label: 'Files & agents', icon: FolderTree },
];

export function WorkspacePage() {
  const { projectId = '' } = useParams();
  const navigate = useNavigate();
  const { projects } = useServices();

  const [tab, setTab] = useState<WorkspaceTab>('preview');
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [modal, setModal] = useState<WorkspaceModal | null>(null);
  const [mobileView, setMobileView] = useState<MobileView>('workspace');

  const loadWorkspace = useCallback(
    () =>
      Promise.all([projects.getProject(projectId), projects.getHistory(projectId), projects.listNotes(projectId)]),
    [projects, projectId],
  );
  const { data, errorMessage, errorCode, isLoading, reload } = useAsyncData(loadWorkspace, 'workspace.load-failed');
  const project = data?.[0] ?? null;
  const isUserProject = project !== null && project.source === 'user';
  const run = useProjectRun(projectId, isUserProject);
  const discovery = useRequirementsSession(projectId, isUserProject);

  if (isLoading && !data) return <LoadingBlock label="Opening workspace" />;

  if (errorMessage) {
    return (
      <div className="mx-auto w-full max-w-xl px-4 py-16">
        <LoadErrorNotice
          title="The workspace could not be loaded"
          message={errorMessage}
          code={errorCode}
          onRetry={reload}
        />
      </div>
    );
  }

  const [, history, notes] = data ?? [null, [], []];

  if (!project) {
    return (
      <EmptyState
        icon={FileQuestion}
        title="Project not found"
        className="flex-1"
        action={<ButtonLink to="/projects">Back to projects</ButtonLink>}
      >
        This project does not exist, or it belongs to another account or another browser.
      </EmptyState>
    );
  }

  const isSample = project.source === 'sample';
  const fileContents = selectedPath === PROJECT_DEFINITION_FILENAME ? projectDefinitionJson(project) : null;

  const openFile = (path: string) => {
    setSelectedPath(path);
    setTab('code');
    setMobileView('workspace');
  };

  const panelVisibility = (view: MobileView) => (mobileView === view ? 'flex' : 'hidden lg:flex');

  return (
    <div className="flex flex-1 flex-col lg:h-[calc(100dvh-3.5rem-1px)] lg:flex-none lg:overflow-hidden">
      {/* Mobile project header */}
      <div className="border-b border-line-soft px-4 py-4 lg:hidden">
        <ProjectSummary project={project} />
        <div className="mt-3 -ml-3">
          <WorkspaceActions layout="row" onOpen={setModal} />
        </div>
        <div role="group" aria-label="Workspace view" className="mt-3 grid grid-cols-3 gap-1 rounded-lg bg-surface p-1">
          {MOBILE_VIEWS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              aria-pressed={mobileView === id}
              onClick={() => setMobileView(id)}
              className={cn(
                'inline-flex h-9 items-center justify-center gap-1.5 rounded-md text-xs font-medium',
                mobileView === id ? 'bg-elevated text-ink' : 'text-muted',
              )}
            >
              <Icon aria-hidden="true" className="size-3.5" />
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        {/* Sidebar: project navigation, explorer, agents */}
        <aside
          aria-label="Project navigation"
          className={cn(
            panelVisibility('files'),
            'min-h-0 flex-col border-line-soft lg:w-64 lg:shrink-0 lg:border-r',
          )}
        >
          <div className="hidden border-b border-line-soft p-4 lg:block">
            <ProjectSummary project={project} />
          </div>
          <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto py-4">
            <FileExplorer rootName={slugify(project.configuration.name)} selectedPath={selectedPath} onOpenFile={openFile} />
            <div className="mt-6 border-t border-line-soft">
              <AgentActivityPanel run={run} />
            </div>
          </div>
          <div className="hidden border-t border-line-soft p-3 lg:block">
            <WorkspaceActions layout="column" onOpen={setModal} />
          </div>
        </aside>

        {/* Chat and requirements */}
        <div
          className={cn(
            panelVisibility('chat'),
            'min-h-[70vh] flex-col border-line-soft lg:min-h-0 lg:w-[340px] lg:shrink-0 lg:border-r',
          )}
        >
          <ChatPanel
            project={project}
            notes={notes}
            readOnly={isSample}
            onAddNote={async (content) => {
              await projects.addNote(project.id, content);
              reload();
            }}
          />
        </div>

        {/* Main work area */}
        <section
          aria-label="Workspace"
          className={cn(panelVisibility('workspace'), 'min-h-[70vh] min-w-0 flex-1 flex-col lg:min-h-0')}
        >
          <div className="flex h-12 shrink-0 items-center border-b border-line-soft px-2 sm:px-3">
            <Tabs idPrefix="workspace" label="Workspace views" items={WORKSPACE_TABS} value={tab} onChange={setTab} />
          </div>
          {isSample && (
            <Notice tone="warning" className="m-3 mb-0">
              This is a sample project (demo data). It is read-only and has never been generated.
            </Notice>
          )}
          <TabPanel idPrefix="workspace" id={tab} className="min-h-0 flex-1 overflow-auto">
            {tab === 'preview' && <PreviewPanel />}
            {tab === 'requirements' && (
              <RequirementsPanel
                discovery={discovery}
                isSample={isSample}
                onOpenPlan={() => {
                  run.reload(); // pick up the newly approved requirements
                  setTab('plan');
                }}
              />
            )}
            {tab === 'plan' && (
              <PlanPanel run={run} isSample={isSample} onOpenRequirements={() => setTab('requirements')} />
            )}
            {tab === 'code' && (
              <CodePanel
                path={selectedPath}
                contents={fileContents}
                onOpenDefinition={() => openFile(PROJECT_DEFINITION_FILENAME)}
              />
            )}
            {tab === 'tasks' && <TasksPanel configuration={project.configuration} />}
            {tab === 'tests' && <TestsPanel />}
            {tab === 'logs' && <LogsPanel history={history} isSample={isSample} />}
          </TabPanel>
        </section>
      </div>

      <HistoryModal open={modal === 'history'} onClose={() => setModal(null)} history={history} isSample={isSample} />
      <ExportModal open={modal === 'export'} onClose={() => setModal(null)} project={project} />
      <SettingsModal
        open={modal === 'settings'}
        onClose={() => setModal(null)}
        project={project}
        onRename={async (name) => {
          await projects.updateProject(project.id, { name });
          reload();
        }}
        onDelete={async () => {
          await projects.deleteProject(project.id);
          setModal(null);
          navigate('/projects', { replace: true });
        }}
      />
    </div>
  );
}
