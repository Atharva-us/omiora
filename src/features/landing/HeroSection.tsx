import { ArrowRight } from 'lucide-react';
import { ButtonLink } from '@/components/ui/Button';
import { ProjectPrompt } from './ProjectPrompt';

export function HeroSection() {
  return (
    <section aria-labelledby="hero-heading" className="relative overflow-hidden">
      <div
        aria-hidden="true"
        className="bg-grid pointer-events-none absolute inset-0 [mask-image:radial-gradient(ellipse_70%_60%_at_30%_20%,black,transparent)]"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-40 left-[12%] size-[520px] rounded-full bg-cyan/[0.07] blur-[120px]"
      />
      <div className="relative mx-auto grid max-w-7xl grid-cols-1 gap-12 px-4 pt-14 pb-20 sm:px-6 sm:pt-20 lg:grid-cols-[1.05fr_1fr] lg:items-center lg:gap-16 lg:px-8 lg:pt-24 lg:pb-28">
        <div className="max-w-xl">
          <p className="inline-flex items-center gap-2 font-mono text-xs tracking-[0.16em] text-cyan">
            <span aria-hidden="true" className="h-px w-6 bg-cyan" />
            YOUR AI SOFTWARE ENGINEERING TEAM
          </p>
          <h1
            id="hero-heading"
            className="mt-6 text-[2.625rem] leading-[1.04] font-semibold tracking-[-0.035em] text-ink sm:text-6xl lg:text-[4.25rem]"
          >
            The Intelligence to Build <span className="text-cyan">Anything.</span>
          </h1>
          <p className="mt-6 text-base leading-relaxed text-muted sm:text-lg">
            Turn your ideas into complete websites, mobile apps, and software systems. Describe what you want to build,
            choose your technology, and let Omniora help engineer the result.
          </p>
          <div className="mt-9 flex flex-col gap-3 sm:flex-row">
            <ButtonLink to="/new" size="lg">
              Start Building
              <ArrowRight aria-hidden="true" />
            </ButtonLink>
            <ButtonLink to={{ hash: 'product' }} variant="secondary" size="lg">
              Explore the Platform
            </ButtonLink>
          </div>
        </div>

        <div className="relative">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-medium text-ink">What do you want to build?</h2>
            <span className="text-xs text-faint">Opens project setup</span>
          </div>
          <ProjectPrompt />
        </div>
      </div>
    </section>
  );
}
