import { useState } from 'react';
import type { CharacterSheet } from '../types';
import { ActionIcon } from './glyphs';
import { sheetFr } from './sheet.fr';

const t = sheetFr.download;

/** Image PNG de la fiche, dessinée dans le navigateur. Le dessin n'est chargé qu'au clic. */
export function DownloadSheet({
  sheet,
  announce,
}: {
  sheet: CharacterSheet;
  announce: (message: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function download() {
    setBusy(true);
    setError(null);
    try {
      const { renderSheetPng, fileSlug } = await import('./exportPng');
      const blob = await renderSheetPng(sheet);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = t.file(fileSlug(sheet.identity.display_name));
      document.body.append(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 10_000);
      announce(t.done);
    } catch {
      setError(t.error);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="sheet-download">
      <button
        type="button"
        className="button button--small"
        onClick={() => void download()}
        disabled={busy}
        aria-describedby="sheet-download-hint"
      >
        <ActionIcon name="download" />
        {busy ? t.busy : t.button}
      </button>
      <p id="sheet-download-hint" className="sheet-download__hint">
        {t.hint}
      </p>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
