import { ArrowRight } from 'lucide-react';
import { ButtonLink } from '@/components/ui/Button';
import { DeveloperSection } from './DeveloperSection';
import { FeaturesSection } from './FeaturesSection';
import { HeroSection } from './HeroSection';
import { HowItWorksSection } from './HowItWorksSection';
import { ProductPreview } from './ProductPreview';

function FinalCta() {
  return (
    <section aria-labelledby="cta-heading" className="border-t border-line-soft">
      <div className="relative mx-auto max-w-7xl overflow-hidden px-4 py-20 sm:px-6 sm:py-28 lg:px-8">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 bottom-0 mx-auto h-64 max-w-3xl rounded-full bg-azure/[0.08] blur-[100px]"
        />
        <div className="relative flex flex-col items-center text-center">
          <h2 id="cta-heading" className="max-w-2xl text-3xl font-semibold tracking-[-0.03em] sm:text-5xl">
            Your next software project starts here.
          </h2>
          <p className="mt-5 max-w-lg text-muted">
            Define the project today. Your configuration is ready for the engine as soon as generation comes online.
          </p>
          <div className="mt-9 flex flex-col gap-3 sm:flex-row">
            <ButtonLink to="/new" size="lg">
              Start Building
              <ArrowRight aria-hidden="true" />
            </ButtonLink>
            <ButtonLink to="/projects" variant="secondary" size="lg">
              View Projects
            </ButtonLink>
          </div>
        </div>
      </div>
    </section>
  );
}

export function LandingPage() {
  return (
    <>
      <HeroSection />
      <ProductPreview />
      <FeaturesSection />
      <HowItWorksSection />
      <DeveloperSection />
      <FinalCta />
    </>
  );
}
