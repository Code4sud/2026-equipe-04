import { ApiError } from '../api/client';
import { fr } from '../content/fr';

export function errorMessage(error: unknown): string {
  return error instanceof ApiError && error.message ? error.message : fr.common.genericError;
}

export function Loading() {
  return (
    <p className="state" role="status">
      {fr.common.loading}
    </p>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="state state--error" role="alert">
      <p>{message}</p>
      {onRetry && (
        <button type="button" className="button" onClick={onRetry}>
          {fr.common.retry}
        </button>
      )}
    </div>
  );
}
