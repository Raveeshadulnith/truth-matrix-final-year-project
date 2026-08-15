import React, { useState } from 'react';
import { CheckIcon, ClipboardIcon, FingerprintIcon } from 'lucide-react';
import type { ForensicEvidence } from '../../api/deepfakeApi';
import {
  EmptyEvidenceMessage,
  EvidenceCard,
  TechnicalDetails,
  WarningList,
} from './ForensicPrimitives';

function CopyButton({ value, label }: { value: string; label: string }) {
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'failed'>('idle');

  const copyValue = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopyState('copied');
    } catch {
      setCopyState('failed');
    }
  };

  return (
    <button
      type="button"
      onClick={() => void copyValue()}
      className="inline-flex flex-none items-center gap-1.5 rounded-lg border border-gray-300 px-2.5 py-1.5 text-xs font-semibold text-gray-700 hover:bg-gray-50 dark:border-navy-600 dark:text-gray-200 dark:hover:bg-navy-700"
      aria-label={`Copy ${label}`}
    >
      {copyState === 'copied' ? <CheckIcon className="h-3.5 w-3.5" /> : <ClipboardIcon className="h-3.5 w-3.5" />}
      {copyState === 'copied' ? 'Copied' : copyState === 'failed' ? 'Copy unavailable' : 'Copy'}
    </button>
  );
}

function FingerprintValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-xl bg-gray-50 p-3 dark:bg-navy-900/60">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
          {label}
        </span>
        <CopyButton value={value} label={label} />
      </div>
      <code className="block whitespace-pre-wrap break-all font-mono text-xs leading-5 text-gray-900 dark:text-gray-100">
        {value}
      </code>
    </div>
  );
}

export function FileFingerprintCard({ evidence }: { evidence: ForensicEvidence }) {
  const fingerprint = evidence.perceptual_fingerprint;
  return (
    <EvidenceCard
      title="File identity & fingerprints"
      status={evidence.file_identity_status}
      description="SHA-256 identifies exact bytes; perceptual fingerprints support similarity review."
    >
      <div className="mb-3 flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
        <FingerprintIcon className="h-4 w-4" />
        <span>{evidence.detected_mime_type ?? 'Detected type unavailable'}</span>
        {evidence.file_size_bytes != null ? (
          <span>· {evidence.file_size_bytes.toLocaleString()} bytes</span>
        ) : null}
      </div>

      <div className="space-y-3">
        {evidence.sha256 ? (
          <FingerprintValue label="SHA-256" value={evidence.sha256} />
        ) : (
          <EmptyEvidenceMessage>An exact file hash was not available.</EmptyEvidenceMessage>
        )}
        {fingerprint.value ? (
          <FingerprintValue label="Perceptual fingerprint" value={fingerprint.value} />
        ) : (
          <EmptyEvidenceMessage>
            Perceptual fingerprint: {fingerprint.status.replace(/_/g, ' ')}.
          </EmptyEvidenceMessage>
        )}
      </div>

      <TechnicalDetails>
        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-gray-500 dark:text-gray-400">Algorithm</dt>
            <dd className="break-words font-medium text-gray-900 dark:text-white">
              {fingerprint.algorithm ?? 'Not available'}
              {fingerprint.algorithm_version ? ` @ ${fingerprint.algorithm_version}` : ''}
            </dd>
          </div>
          <div>
            <dt className="text-gray-500 dark:text-gray-400">Hash size</dt>
            <dd className="font-medium text-gray-900 dark:text-white">
              {fingerprint.hash_size != null ? `${fingerprint.hash_size} bits` : 'Not available'}
            </dd>
          </div>
          <div>
            <dt className="text-gray-500 dark:text-gray-400">Components</dt>
            <dd className="font-medium text-gray-900 dark:text-white">
              {fingerprint.components.length}
            </dd>
          </div>
          <div>
            <dt className="text-gray-500 dark:text-gray-400">Fingerprint duration</dt>
            <dd className="font-medium text-gray-900 dark:text-white">
              {fingerprint.duration_seconds != null
                ? `${fingerprint.duration_seconds.toFixed(2)} seconds`
                : 'Not applicable'}
            </dd>
          </div>
        </dl>
        {fingerprint.components.length > 0 ? (
          <div className="mt-3 max-h-44 overflow-auto rounded-lg bg-gray-950 p-3 font-mono text-xs text-gray-100">
            {fingerprint.components.map((component) => (
              <div key={`${component.index}-${component.value}`} className="break-all">
                #{component.index} {component.timestamp_seconds != null ? `@ ${component.timestamp_seconds.toFixed(3)}s ` : ''}
                {component.value}
              </div>
            ))}
          </div>
        ) : null}
      </TechnicalDetails>
      <WarningList warnings={fingerprint.warnings} />
    </EvidenceCard>
  );
}
