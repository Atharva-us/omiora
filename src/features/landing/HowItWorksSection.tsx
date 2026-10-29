import { STEPS } from './content';

export function HowItWorksSection() {
  return (
    <section
      id="how-it-works"
      aria-labelledby="how-heading"
      className="border-t border-line-soft bg-surface/40 py-20 sm:py-28"
    >
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="max-w-2xl">
          <p className="font-mono text-xs tracking-[0.16em] text-cyan">HOW IT WORKS</p>
          <h2 id="how-heading" className="mt-4 text-3xl font-semibold tracking-[-0.025em] sm:text-4xl">
            From a sentence to a repository in four stages.
          </h2>
        </div>

        <ol className="mt-14 grid gap-10 md:grid-cols-2 lg:grid-cols-4 lg:gap-8">
          {STEPS.map((step, index) => (
            <li key={step.title} className="relative">
              <div className="flex items-center gap-4">
                <span className="flex size-9 items-center justify-center rounded-md border border-cyan/40 bg-cyan/[0.06] font-mono text-sm text-cyan">
                  {String(index + 1).padStart(2, '0')}
                </span>
                {index < STEPS.length - 1 && (
                  <span aria-hidden="true" className="hidden h-px flex-1 bg-gradient-to-r from-line to-transparent lg:block" />
                )}
              </div>
              <h3 className="mt-5 text-base font-semibold text-ink">{step.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted">{step.description}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
