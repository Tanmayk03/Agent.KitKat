import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { CheckCircle2, AlertTriangle, Info, X, Loader2 } from 'lucide-react';

/*
 * App-wide feedback: toasts (replacing alert()) and a confirm dialog (replacing confirm()).
 *
 *   const toast = useToast();   toast.success('Saved'); toast.error(err.message);
 *   const confirm = useConfirm(); if (await confirm({ title, body, confirmLabel, danger })) { ... }
 *
 * Also exports small shared state components: <Loading/>, <EmptyState/>, <ErrorState/>.
 */

const FeedbackContext = createContext(null);

const TONES = {
  success: { icon: CheckCircle2, cls: 'border-emerald-800/60 bg-emerald-950/90 text-emerald-100', iconCls: 'text-emerald-400' },
  error: { icon: AlertTriangle, cls: 'border-red-800/60 bg-red-950/95 text-red-100', iconCls: 'text-red-400' },
  info: { icon: Info, cls: 'border-zinc-700 bg-zinc-900/95 text-zinc-100', iconCls: 'text-zinc-400' },
};

let nextId = 1;

export function FeedbackProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const [dialog, setDialog] = useState(null);
  const timers = useRef({});

  const dismiss = useCallback((id) => {
    clearTimeout(timers.current[id]);
    delete timers.current[id];
    setToasts((t) => t.filter((x) => x.id !== id));
  }, []);

  const push = useCallback((tone, message, opts = {}) => {
    const id = nextId++;
    setToasts((t) => [...t.slice(-3), { id, tone, message: String(message || ''), title: opts.title }]);
    // Errors stay longer so they can be read; nothing important disappears in under 4 s.
    const ms = opts.duration ?? (tone === 'error' ? 8000 : 4000);
    if (ms > 0) timers.current[id] = setTimeout(() => dismiss(id), ms);
    return id;
  }, [dismiss]);

  const toast = useRef(null);
  toast.current = {
    success: (m, o) => push('success', m, o),
    error: (m, o) => push('error', m, o),
    info: (m, o) => push('info', m, o),
    dismiss,
  };

  const confirm = useCallback((opts) => new Promise((resolve) => {
    setDialog({ ...opts, resolve });
  }), []);

  const closeDialog = (result) => {
    dialog?.resolve(result);
    setDialog(null);
  };

  const value = useRef({});
  value.current.toast = toast.current;
  value.current.confirm = confirm;

  return (
    <FeedbackContext.Provider value={value.current}>
      {children}

      {/* Toasts: top-right on desktop, above the bottom nav on phones */}
      <div
        className="fixed z-[70] right-3 left-3 sm:left-auto sm:w-96 bottom-20 lg:bottom-auto lg:top-20 flex flex-col gap-2 pointer-events-none"
        role="region"
        aria-label="Notifications"
      >
        {toasts.map((t) => {
          const tone = TONES[t.tone] || TONES.info;
          const Icon = tone.icon;
          return (
            <div
              key={t.id}
              role={t.tone === 'error' ? 'alert' : 'status'}
              className={`pointer-events-auto flex items-start gap-2.5 rounded-lg border px-3.5 py-3 shadow-lg backdrop-blur text-xs sm:text-sm ${tone.cls}`}
            >
              <Icon className={`w-4 h-4 mt-0.5 shrink-0 ${tone.iconCls}`} />
              <div className="flex-1 min-w-0">
                {t.title && <div className="font-semibold mb-0.5">{t.title}</div>}
                <div className="break-words whitespace-pre-line">{t.message}</div>
              </div>
              <button onClick={() => dismiss(t.id)} className="p-0.5 opacity-70 hover:opacity-100" aria-label="Dismiss">
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          );
        })}
      </div>

      {dialog && <ConfirmDialog {...dialog} onClose={closeDialog} />}
    </FeedbackContext.Provider>
  );
}

function ConfirmDialog({ title = 'Are you sure?', body, confirmLabel = 'Confirm', cancelLabel = 'Cancel', danger = false, onClose }) {
  const confirmRef = useRef(null);
  useEffect(() => {
    confirmRef.current?.focus();
    const onKey = (e) => { if (e.key === 'Escape') onClose(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-[80] flex items-end sm:items-center justify-center bg-black/60 p-3" onClick={() => onClose(false)}>
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        className="w-full sm:max-w-md rounded-xl border border-zinc-700 bg-zinc-900 p-5 space-y-4 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="confirm-title" className="text-sm sm:text-base font-semibold text-zinc-100">{title}</h2>
        {body && <div className="text-xs sm:text-sm text-zinc-300 leading-relaxed whitespace-pre-line">{body}</div>}
        <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2">
          <button onClick={() => onClose(false)} className="px-4 py-2.5 sm:py-2 rounded-lg text-sm border border-zinc-700 text-zinc-200 hover:bg-zinc-800">
            {cancelLabel}
          </button>
          <button
            ref={confirmRef}
            onClick={() => onClose(true)}
            className={`px-4 py-2.5 sm:py-2 rounded-lg text-sm font-medium ${danger ? 'bg-red-700 hover:bg-red-600 text-white' : 'bg-zinc-100 hover:bg-zinc-200 text-zinc-950'}`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export function useToast() {
  const ctx = useContext(FeedbackContext);
  if (!ctx) throw new Error('useToast must be used inside <FeedbackProvider>');
  return ctx.toast;
}

export function useConfirm() {
  const ctx = useContext(FeedbackContext);
  if (!ctx) throw new Error('useConfirm must be used inside <FeedbackProvider>');
  return ctx.confirm;
}

export function Loading({ label = 'Loading…', className = '' }) {
  return (
    <div className={`py-14 flex items-center justify-center gap-2 text-zinc-500 text-xs sm:text-sm ${className}`} role="status">
      <Loader2 className="w-4 h-4 animate-spin" />
      <span>{label}</span>
    </div>
  );
}

export function EmptyState({ title, children, action }) {
  return (
    <div className="py-14 px-4 text-center rounded-xl border border-dashed border-zinc-800">
      <p className="text-sm text-zinc-300 font-medium">{title}</p>
      {children && <div className="text-xs text-zinc-500 mt-1.5 max-w-md mx-auto leading-relaxed">{children}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({ message, onRetry }) {
  return (
    <div className="p-4 rounded-xl border border-red-900/60 bg-red-950/20 text-xs sm:text-sm flex flex-col sm:flex-row sm:items-center gap-3 justify-between" role="alert">
      <span className="text-red-300">{message || 'Something went wrong.'}</span>
      {onRetry && (
        <button onClick={onRetry} className="px-3 py-1.5 rounded-lg border border-red-800 text-red-200 hover:bg-red-900/40 text-xs">
          Try again
        </button>
      )}
    </div>
  );
}
