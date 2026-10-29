import { Link } from 'react-router-dom';
import { cn } from '@/lib/cn';
// The original brand asset lives at the project root and is imported in place.
import logoUrl from '../../../logo.png';

const LOGO_ASPECT = 110 / 115;

interface LogoMarkProps {
  /** Rendered height in pixels; width follows the native 110×115 aspect ratio. */
  size?: number;
  className?: string;
}

export function LogoMark({ size = 32, className }: LogoMarkProps) {
  return (
    <img
      src={logoUrl}
      alt=""
      width={Math.round(size * LOGO_ASPECT)}
      height={size}
      className={cn('shrink-0 rounded-md ring-1 ring-white/5', className)}
      draggable={false}
    />
  );
}

interface LogoProps {
  to?: string;
  size?: number;
  className?: string;
}

export function Logo({ to = '/', size = 32, className }: LogoProps) {
  return (
    <Link
      to={to}
      className={cn('inline-flex items-center gap-2.5 rounded-md text-ink', className)}
      aria-label="Omniora home"
    >
      <LogoMark size={size} />
      <span className="text-[1.0625rem] font-semibold tracking-[-0.01em]">Omniora</span>
    </Link>
  );
}
