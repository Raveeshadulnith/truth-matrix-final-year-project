import React from 'react';
import {
  AlertCircleIcon,
  CheckCircle2Icon,
  CircleHelpIcon,
  InfoIcon,
  MinusCircleIcon,
} from 'lucide-react';
import type { JsonObject, JsonValue } from '../../api/deepfakeApi';
import { humanizeForensicLabel, redactSensitiveJson } from '../../utils/forensicEvidence';

type StatusTone = 'positive' | 'negative' | 'caution' | 'neutral' | 'info';

const STATUS_TONES: Record<string, StatusTone> = {
  complete: 'positive',
  available: 'positive',
  valid: 'positive',
  trusted: 'positive',
  success: 'positive',
  invalid: 'negative',
  error: 'negative',
  untrusted: 'caution',
  partial: 'caution',
  failure: 'negative',
  informational: 'info',
  info: 'info',
  low: 'neutral',
  medium: 'caution',
  high: 'negative',
  exact: 'positive',
  near: 'info',
  not_present: 'neutral',
  not_applicable: 'neutral',
  not_checked: 'neutral',
  unsupported: 'neutral',
  unavailable: 'neutral',
  unknown: 'neutral',
};

const TONE_STYLES: Record<StatusTone, string> = {
  positive:
    'border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300',
  negative:
    'border-red-300 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950/35 dark:text-red-300',
  caution:
    'border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-700 dark:bg-amber-950/35 dark:text-amber-300',
  neutral:
    'border-gray-300 bg-gray-50 text-gray-700 dark:border-navy-600 dark:bg-navy-900/60 dark:text-gray-300',
  info:
    'border-cyan-300 bg-cyan-50 text-cyan-900 dark:border-cyan-800 dark:bg-cyan-950/35 dark:text-cyan-300',
};

function statusIcon(tone: StatusTone) {
  const className = 'h-3.5 w-3.5 flex-none';
  if (tone === 'positive') return <CheckCircle2Icon className={className} />;
  if (tone === 'negative') return <AlertCircleIcon className={className} />;
  if (tone === 'caution') return <CircleHelpIcon className={className} />;
  if (tone === 'info') return <InfoIcon className={className} />;
  return <MinusCircleIcon className={className} />;
}

export function ForensicStatusBadge({
  status,
  label,
}: {
  status: string;
  label?: string;
}) {
  const tone = STATUS_TONES[status] ?? 'neutral';
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${TONE_STYLES[tone]}`}
      data-status={status}
    >
      {statusIcon(tone)}
      {label ?? humanizeForensicLabel(status)}
    </span>
  );
}

export function EvidenceCard({
  title,
  status,
  description,
  children,
  className = '',
}: {
  title: string;
  status?: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`min-w-0 rounded-2xl border border-gray-200 bg-white p-4 shadow-sm dark:border-navy-700 dark:bg-navy-800 sm:p-5 ${className}`}
      aria-label={title}
    >
      <div className="mb-4 flex flex-col items-start justify-between gap-2 sm:flex-row sm:items-center">
        <div className="min-w-0">
          <h3 className="font-semibold text-gray-900 dark:text-white">{title}</h3>
          {description ? (
            <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{description}</p>
          ) : null}
        </div>
        {status ? <ForensicStatusBadge status={status} /> : null}
      </div>
      {children}
    </section>
  );
}

export function EmptyEvidenceMessage({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded-xl border border-gray-200 bg-gray-50 p-3 text-sm text-gray-600 dark:border-navy-700 dark:bg-navy-900/50 dark:text-gray-300">
      {children}
    </p>
  );
}

export function TechnicalDetails({
  label = 'Technical details',
  children,
}: {
  label?: string;
  children: React.ReactNode;
}) {
  return (
    <details className="group mt-3 rounded-xl border border-gray-200 dark:border-navy-700">
      <summary className="cursor-pointer select-none px-3 py-2 text-sm font-medium text-gray-700 marker:text-gray-400 hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-navy-700/50">
        {label}
      </summary>
      <div className="border-t border-gray-200 p-3 dark:border-navy-700">{children}</div>
    </details>
  );
}

function textValue(value: JsonValue): string {
  if (typeof value === 'string') return value;
  if (value === null) return 'Not available';
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return JSON.stringify(value, null, 2);
}

export function SafeJsonFields({ value }: { value: JsonObject }) {
  const safeValue = redactSensitiveJson(value) as JsonObject;
  const entries = Object.entries(safeValue).sort(([left], [right]) =>
    left.localeCompare(right)
  );
  if (entries.length === 0) {
    return <EmptyEvidenceMessage>No fields were returned.</EmptyEvidenceMessage>;
  }
  return (
    <dl className="grid min-w-0 gap-3 sm:grid-cols-2">
      {entries.map(([key, value]) => (
        <div key={key} className="min-w-0 rounded-lg bg-gray-50 p-3 dark:bg-navy-900/60">
          <dt className="break-words text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
            {humanizeForensicLabel(key)}
          </dt>
          <dd className="mt-1 whitespace-pre-wrap break-words text-sm text-gray-900 dark:text-gray-100">
            {textValue(value)}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function WarningList({ warnings }: { warnings: string[] }) {
  if (warnings.length === 0) return null;
  return (
    <ul className="mt-3 space-y-1 text-sm text-amber-800 dark:text-amber-300">
      {warnings.map((warning, index) => (
        <li key={`${warning}-${index}`} className="flex gap-2">
          <InfoIcon className="mt-0.5 h-4 w-4 flex-none" aria-hidden="true" />
          <span className="break-words">{warning}</span>
        </li>
      ))}
    </ul>
  );
}
