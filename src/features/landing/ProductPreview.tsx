import { ChevronRight, Circle, CircleCheck, CircleDot, File, Folder, Monitor } from 'lucide-react';
import { cn } from '@/lib/cn';

/**
 * ILLUSTRATIVE MOCKUP. A static picture of the intended workspace, not live
 * output. Nothing here is generated, and the page labels it as a demonstration.
 */

const tree = [
  { depth: 0, name: 'atelier-commerce', folder: true },
  { depth: 1, name: 'src', folder: true },
  { depth: 2, name: 'app', folder: true },
  { depth: 3, name: 'page.tsx', folder: false, active: true },
  { depth: 3, name: 'layout.tsx', folder: false },
  { depth: 2, name: 'components', folder: true },
  { depth: 3, name: 'ProductGrid.tsx', folder: false },
  { depth: 3, name: 'CartDrawer.tsx', folder: false },
  { depth: 1, name: 'tests', folder: true },
  { depth: 1, name: 'package.json', folder: false },
];

const pipeline = [
  { label: 'Requirements analysed', state: 'done' },
  { label: 'Architecture planned', state: 'done' },
  { label: 'Interface components', state: 'active' },
  { label: 'API and data layer', state: 'pending' },
  { label: 'Test suite', state: 'pending' },
  { label: 'Package for export', state: 'pending' },
] as const;

function PipelineIcon({ state }: { state: (typeof pipeline)[number]['state'] }) {
  if (state === 'done') return <CircleCheck aria-hidden="true" className="size-3.5 text-success" />;
  if (state === 'active') return <CircleDot aria-hidden="true" className="size-3.5 text-cyan" />;
  return <Circle aria-hidden="true" className="size-3.5 text-faint" />;
}

export function ProductPreview() {
  return (
    <section id="product" aria-labelledby="product-heading" className="relative border-t border-line-soft py-20 sm:py-28">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl">
            <p className="font-mono text-xs tracking-[0.16em] text-cyan">THE WORKSPACE</p>
            <h2 id="product-heading" className="mt-4 text-3xl font-semibold tracking-[-0.025em] sm:text-4xl">
              One surface for requirements, code, preview, and verification.
            </h2>
            <p className="mt-4 text-muted">
              The Omniora workspace keeps the conversation, the file tree, the running application, and every build and
              test result side by side, so you can see what changed and why.
            </p>
          </div>
          <p className="inline-flex shrink-0 items-center gap-2 self-start rounded-md border border-warning/30 bg-warning/[0.06] px-3 py-1.5 text-xs text-warning lg:self-auto">
            <span aria-hidden="true" className="size-1.5 rounded-full bg-warning" />
            Illustrative mockup, not live output
          </p>
        </div>

        <figure className="mt-12">
          <div
            role="img"
            aria-label="Illustration of the Omniora workspace: a prompt panel, a file explorer, a storefront preview, and a build pipeline panel."
            className="overflow-hidden rounded-xl border border-line bg-surface shadow-panel"
          >
            {/* Window chrome */}
            <div className="flex h-10 items-center gap-3 border-b border-line-soft bg-[#0a0e17] px-4">
              <div aria-hidden="true" className="flex gap-1.5">
                <span className="size-2.5 rounded-full bg-line" />
                <span className="size-2.5 rounded-full bg-line" />
                <span className="size-2.5 rounded-full bg-line" />
              </div>
              <div className="flex items-center gap-1.5 text-xs text-faint">
                <span>Projects</span>
                <ChevronRight aria-hidden="true" className="size-3" />
                <span className="text-muted">Atelier Commerce</span>
              </div>
            </div>

            <div className="grid min-h-[440px] grid-cols-1 md:grid-cols-[220px_1fr] lg:grid-cols-[220px_1fr_260px]">
              {/* Explorer + prompt */}
              <div className="hidden flex-col border-r border-line-soft md:flex">
                <div className="border-b border-line-soft p-3">
                  <p className="mb-2 text-[0.6875rem] font-medium tracking-wider text-faint uppercase">Prompt</p>
                  <p className="rounded-md border border-line bg-elevated p-2.5 text-xs leading-relaxed text-muted">
                    Premium fashion storefront with curated collections, a slide-out cart, and Stripe checkout.
                  </p>
                </div>
                <div className="p-3">
                  <p className="mb-2 text-[0.6875rem] font-medium tracking-wider text-faint uppercase">Explorer</p>
                  <ul className="space-y-0.5 font-mono text-[0.71875rem]">
                    {tree.map((node) => (
                      <li
                        key={`${node.depth}-${node.name}`}
                        className={cn(
                          'flex items-center gap-1.5 rounded px-1.5 py-1',
                          'active' in node && node.active ? 'bg-cyan/10 text-ink' : 'text-muted',
                        )}
                        style={{ paddingLeft: `${node.depth * 12 + 6}px` }}
                      >
                        {node.folder ? (
                          <Folder aria-hidden="true" className="size-3.5 text-azure" />
                        ) : (
                          <File aria-hidden="true" className="size-3.5 text-faint" />
                        )}
                        {node.name}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* Preview */}
              <div className="flex flex-col bg-obsidian/40">
                <div className="flex h-9 items-center gap-4 border-b border-line-soft px-4 text-xs">
                  <span className="flex items-center gap-1.5 text-ink">
                    <Monitor aria-hidden="true" className="size-3.5 text-cyan" />
                    Preview
                  </span>
                  <span className="text-faint">Code</span>
                  <span className="text-faint">Tests</span>
                  <span className="text-faint">Logs</span>
                </div>
                <div className="flex-1 p-4 sm:p-6">
                  <div className="h-full rounded-lg border border-line-soft bg-[#f4f1ec] p-4 text-[#1c1a17] sm:p-5">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-semibold tracking-[0.2em]">ATELIER</span>
                      <div className="hidden gap-4 text-[0.6875rem] text-[#6b655c] sm:flex">
                        <span>Women</span>
                        <span>Men</span>
                        <span>Collections</span>
                        <span>Cart (2)</span>
                      </div>
                    </div>
                    <div className="mt-5 grid gap-4 sm:grid-cols-[1.2fr_1fr]">
                      <div className="flex flex-col justify-end rounded-md bg-[#d9d2c7] p-4 sm:min-h-40">
                        <p className="text-[0.625rem] tracking-[0.2em] text-[#6b655c]">AUTUMN EDIT</p>
                        <p className="mt-1 text-lg leading-tight font-semibold">Considered layers for the season</p>
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        {['#c8bfb2', '#b7aea1', '#a89f93', '#d3ccc2'].map((tone) => (
                          <div key={tone} className="space-y-1.5">
                            <div className="aspect-[4/5] rounded" style={{ backgroundColor: tone }} />
                            <div className="h-1.5 w-3/4 rounded-full bg-[#cfc8bd]" />
                            <div className="h-1.5 w-1/3 rounded-full bg-[#ddd7ce]" />
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Build status */}
              <div className="hidden border-l border-line-soft p-4 lg:block">
                <p className="mb-3 text-[0.6875rem] font-medium tracking-wider text-faint uppercase">Build pipeline</p>
                <ol className="space-y-3">
                  {pipeline.map((step) => (
                    <li key={step.label} className="flex items-center gap-2.5 text-xs">
                      <PipelineIcon state={step.state} />
                      <span className={step.state === 'pending' ? 'text-faint' : 'text-muted'}>{step.label}</span>
                    </li>
                  ))}
                </ol>
                <div className="mt-6 rounded-md border border-line-soft bg-obsidian/60 p-3 font-mono text-[0.6875rem] leading-relaxed text-faint">
                  <p>
                    <span className="text-cyan">frontend</span> writing ProductGrid.tsx
                  </p>
                  <p>
                    <span className="text-azure">reviewer</span> queued
                  </p>
                </div>
              </div>
            </div>
          </div>
          <figcaption className="mt-4 text-center text-xs text-faint">
            Static illustration of the planned workspace. The real workspace opens when you create a project.
          </figcaption>
        </figure>
      </div>
    </section>
  );
}
