import '@testing-library/jest-dom/vitest';
import { cleanup, configure } from '@testing-library/react';
import { afterEach } from 'vitest';

// The workspace route is lazy-loaded; the first test in a file pays for compiling that chunk
// under jsdom, which can exceed Testing Library's 1 s default for `findBy*`.
configure({ asyncUtilTimeout: 5000 });

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  window.sessionStorage.clear();
});

// jsdom does not implement scrollTo / matchMedia.
window.scrollTo = () => {};
if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList;
}
