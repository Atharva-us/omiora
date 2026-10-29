/**
 * Saves text as a file via a temporary object URL. The filename must already
 * be sanitised by the caller. The URL is revoked on the next task: revoking
 * synchronously after `click()` can abort the download in some browsers.
 */
export function downloadTextFile(filename: string, contents: string, mimeType: string): void {
  const url = URL.createObjectURL(new Blob([contents], { type: mimeType }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = 'noopener';
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}
