import { useNavigate } from 'react-router-dom';
import { LogOut } from 'lucide-react';
import { Button, ButtonLink } from '@/components/ui/Button';
import { useSession } from '@/hooks/use-session';

/** "Sign In" when signed out; the account name and a sign-out button when signed in. */
export function AccountControl({ size = 'sm' }: { size?: 'sm' | 'md' }) {
  const { user, signOut } = useSession();
  const navigate = useNavigate();
  if (!user) {
    return (
      <ButtonLink to="/sign-in" variant="ghost" size={size}>
        Sign In
      </ButtonLink>
    );
  }
  return (
    <div className="flex items-center gap-2">
      <span className="hidden max-w-40 truncate text-sm text-muted sm:inline" title={user.email}>
        {user.name}
      </span>
      <Button
        variant="ghost"
        size={size}
        onClick={async () => {
          await signOut();
          navigate('/');
        }}
      >
        <LogOut aria-hidden="true" />
        Sign out
      </Button>
    </div>
  );
}
