import { Code2, GitBranch, ShieldCheck, TestTubeDiagonal } from 'lucide-react';

const principles = [
  {
    icon: Code2,
    title: 'Readable code you own',
    description: 'Conventional project layouts and idiomatic code, with no hidden runtime and no proprietary format.',
  },
  {
    icon: GitBranch,
    title: 'Architecture you can steer',
    description: 'Review the plan before code is written. Override the stack, structure, and conventions at any point.',
  },
  {
    icon: TestTubeDiagonal,
    title: 'Tests as a first-class output',
    description: 'Test suites ship with the code, and results are reported as they happen, failures included.',
  },
  {
    icon: ShieldCheck,
    title: 'Isolated execution',
    description:
      'Generated code runs only in resource-limited sandboxes with restricted network access, never on shared servers.',
  },
];

const configExample = `{
  "name": "Stride Fitness",
  "platform": "mobile",
  "stack": {
    "mode": "custom",
    "technologies": ["flutter", "fastapi", "postgresql"]
  },
  "requirements": {
    "features": ["authentication", "database", "notifications"],
    "custom": "Offline workout logging"
  }
}`;

export function DeveloperSection() {
  return (
    <section id="developers" aria-labelledby="developers-heading" className="border-t border-line-soft py-20 sm:py-28">
      <div className="mx-auto grid max-w-7xl grid-cols-1 gap-14 px-4 sm:px-6 lg:grid-cols-2 lg:gap-20 lg:px-8">
        <div className="min-w-0">
          <p className="font-mono text-xs tracking-[0.16em] text-cyan">FOR DEVELOPERS</p>
          <h2 id="developers-heading" className="mt-4 text-3xl font-semibold tracking-[-0.025em] sm:text-4xl">
            Automation without giving up control.
          </h2>
          <p className="mt-4 text-muted">
            Omniora is built for people who care about what ships. The goal is to automate the repetitive work while
            leaving every decision about code, architecture, testing, and ownership in your hands.
          </p>
          <ul className="mt-10 grid gap-7 sm:grid-cols-2">
            {principles.map(({ icon: Icon, title, description }) => (
              <li key={title}>
                <Icon aria-hidden="true" className="size-5 text-cyan" strokeWidth={1.75} />
                <h3 className="mt-3 text-sm font-semibold text-ink">{title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-muted">{description}</p>
              </li>
            ))}
          </ul>
        </div>

        <div className="min-w-0 lg:pt-10">
          <div className="overflow-hidden rounded-xl border border-line bg-surface shadow-panel">
            <div className="flex items-center justify-between border-b border-line-soft px-4 py-2.5">
              <span className="font-mono text-xs text-muted">omniora.project.json</span>
              <span className="text-xs text-faint">Project definition</span>
            </div>
            <pre className="scrollbar-thin overflow-x-auto p-5 font-mono text-[0.8125rem] leading-relaxed text-muted">
              <code>{configExample}</code>
            </pre>
          </div>
          <p className="mt-4 text-sm leading-relaxed text-faint">
            Every project starts as a plain, versionable definition like this one. You can download it from any
            project you create today.
          </p>
        </div>
      </div>
    </section>
  );
}
