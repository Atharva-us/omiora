export interface SectionLink {
  label: string;
  hash: string;
}

/** Landing-page sections reachable from the marketing navbar. */
export const SECTION_LINKS: readonly SectionLink[] = [
  { label: 'Product', hash: 'product' },
  { label: 'Features', hash: 'features' },
  { label: 'How It Works', hash: 'how-it-works' },
  { label: 'Developers', hash: 'developers' },
];
