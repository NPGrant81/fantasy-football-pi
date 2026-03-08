/* ignore-breakpoints */

export default function InlineError({ title = 'Something went wrong', message, onRetry }) {
  return (
    <div className="rounded-lg border border-rose-900 bg-rose-950/30 p-4 text-sm text-rose-300" role="alert">
      <div className="font-bold">{title}</div>
      {message ? <div className="mt-1">{message}</div> : null}
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded border border-rose-700 px-3 py-1 text-xs font-bold uppercase tracking-wide text-rose-200 hover:bg-rose-900/40"
        >
          Retry
        </button>
      ) : null}
    </div>
  );
}
