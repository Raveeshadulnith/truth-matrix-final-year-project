import { useState } from 'react';
import { CheckIcon, ClipboardIcon, WrenchIcon } from 'lucide-react';
import type { CreationInfo, ForensicEvidence, ForensicFinding } from '../../api/deepfakeApi';
import { formatFileSize } from '../../utils/formatters';
import { humanizeForensicLabel } from '../../utils/forensicEvidence';
import { ForensicStatusBadge, SafeJsonFields } from './ForensicPrimitives';

function CopyTechnicalValue({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };
  return (
    <button
      type="button"
      onClick={() => void copy()}
      aria-label={`Copy ${label}`}
      className="inline-flex items-center gap-1 rounded-md border border-gray-300 px-2 py-1 text-xs font-medium hover:bg-gray-50 dark:border-navy-600 dark:hover:bg-navy-700"
    >
      {copied ? <CheckIcon className="h-3.5 w-3.5" /> : <ClipboardIcon className="h-3.5 w-3.5" />}
      {copied ? 'Copied' : 'Copy'}
    </button>
  );
}

function TechnicalFinding({ finding }: { finding: ForensicFinding }) {
  return (
    <li className="rounded-lg border border-gray-200 p-3 dark:border-navy-700">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-medium text-gray-900 dark:text-white">{finding.title}</p>
          <p className="mt-1 break-all font-mono text-xs text-gray-500 dark:text-gray-400">{finding.code}</p>
        </div>
        <ForensicStatusBadge status={finding.severity} />
      </div>
      <p className="mt-2 text-sm leading-relaxed text-gray-700 dark:text-gray-300">{finding.explanation}</p>
      <dl className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
        <div><dt className="text-gray-500">Method</dt><dd className="break-words">{finding.method ?? 'Not specified'}</dd></div>
        <div><dt className="text-gray-500">Version</dt><dd className="break-words">{finding.method_version ?? 'Not specified'}</dd></div>
      </dl>
      <div className="mt-3"><SafeJsonFields value={finding.evidence} /></div>
      {finding.limitations.length > 0 ? (
        <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-gray-600 dark:text-gray-400">
          {finding.limitations.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}
        </ul>
      ) : null}
    </li>
  );
}

function TechnicalOriginDetails({ creation }: { creation: CreationInfo }) {
  return (
    <dl className="mt-2 grid gap-2 text-sm sm:grid-cols-2">
      <div><dt className="text-gray-500">Device make</dt><dd>{creation.device_make ?? 'Not embedded'}</dd></div>
      <div><dt className="text-gray-500">Device model</dt><dd>{creation.device_model ?? 'Not embedded'}</dd></div>
      <div><dt className="text-gray-500">Creator</dt><dd>{creation.creator ?? 'Not embedded'}</dd></div>
      <div><dt className="text-gray-500">Capture time</dt><dd>{creation.created_at ?? 'Not embedded'}</dd></div>
      <div><dt className="text-gray-500">Digitized time</dt><dd>{creation.digitized_at ?? 'Not embedded'}</dd></div>
      <div><dt className="text-gray-500">Modified time</dt><dd>{creation.modified_at ?? 'Not embedded'}</dd></div>
      <div><dt className="text-gray-500">Timezone present</dt><dd>{creation.timezone_present ? 'Yes' : 'No'}</dd></div>
      <div><dt className="text-gray-500">Location present</dt><dd>{creation.location_present ? 'Yes, coordinates hidden' : 'No'}</dd></div>
    </dl>
  );
}

export function ForensicTechnicalDetails({ evidence }: { evidence: ForensicEvidence }) {
  const fingerprint = evidence.perceptual_fingerprint;
  const sourceTags = evidence.creation_info.source_tags;
  const collectionWarnings = [
    ...evidence.warnings,
    ...evidence.metadata.warnings,
    ...evidence.c2pa.warnings,
    ...fingerprint.warnings,
  ];

  return (
    <details className="group rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-navy-700 dark:bg-navy-800">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded-2xl p-4 font-semibold text-gray-900 hover:bg-gray-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500 dark:text-white dark:hover:bg-navy-700/50 sm:p-5">
        <span className="flex items-center gap-2"><WrenchIcon className="h-5 w-5 text-gray-500" />Technical details</span>
        <span className="text-xs font-normal text-gray-500 dark:text-gray-400">Hashes, metadata, methods, and measurements</span>
      </summary>
      <div className="space-y-7 border-t border-gray-200 p-4 dark:border-navy-700 sm:p-5">
        <section aria-labelledby="technical-file-heading">
          <h4 id="technical-file-heading" className="font-semibold text-gray-900 dark:text-white">File identity and fingerprints</h4>
          <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
            <div><dt className="text-gray-500">Original filename</dt><dd className="break-words">{evidence.original_filename ?? 'Unavailable'}</dd></div>
            <div><dt className="text-gray-500">Detected MIME type</dt><dd>{evidence.detected_mime_type ?? 'Unavailable'}</dd></div>
            <div><dt className="text-gray-500">Byte size</dt><dd>{evidence.file_size_bytes != null ? `${formatFileSize(evidence.file_size_bytes)} (${evidence.file_size_bytes.toLocaleString()} bytes)` : 'Unavailable'}</dd></div>
            <div><dt className="text-gray-500">Schema version</dt><dd>{evidence.schema_version}</dd></div>
            <div><dt className="text-gray-500">Collection time</dt><dd>{evidence.processing_time_ms.toLocaleString()} ms</dd></div>
          </dl>
          {evidence.sha256 ? (
            <div className="mt-3 rounded-lg bg-gray-50 p-3 dark:bg-navy-900/60">
              <div className="flex items-center justify-between gap-2"><span className="text-xs font-semibold text-gray-500">SHA-256</span><CopyTechnicalValue value={evidence.sha256} label="SHA-256" /></div>
              <code className="mt-2 block break-all text-xs">{evidence.sha256}</code>
            </div>
          ) : null}
          <div className="mt-3 rounded-lg bg-gray-50 p-3 dark:bg-navy-900/60">
            <div className="flex items-center justify-between gap-2"><span className="text-xs font-semibold text-gray-500">Perceptual fingerprint</span>{fingerprint.value ? <CopyTechnicalValue value={fingerprint.value} label="perceptual fingerprint" /> : null}</div>
            <code className="mt-2 block break-all text-xs">{fingerprint.value ?? fingerprint.status.replace(/_/g, ' ')}</code>
            <p className="mt-2 text-xs text-gray-500">{fingerprint.algorithm ?? 'Algorithm unavailable'}{fingerprint.algorithm_version ? ` version ${fingerprint.algorithm_version}` : ''}{fingerprint.hash_size ? `, ${fingerprint.hash_size} bits` : ''}</p>
          </div>
          {fingerprint.components.length > 0 ? (
            <div className="mt-3 max-h-48 overflow-auto rounded-lg bg-gray-950 p-3 font-mono text-xs text-gray-100">
              {fingerprint.components.map((component) => <div key={`${component.index}-${component.value}`} className="break-all">#{component.index}{component.timestamp_seconds != null ? ` at ${component.timestamp_seconds.toFixed(3)}s` : ''}: {component.value}</div>)}
            </div>
          ) : null}
        </section>

        <section aria-labelledby="technical-metadata-heading">
          <h4 id="technical-metadata-heading" className="font-semibold text-gray-900 dark:text-white">Metadata and source tags</h4>
          <p className="mt-1 text-xs text-gray-500">Source: {evidence.metadata.source ?? 'Unavailable'}; extractor version: {evidence.metadata.source_version ?? 'Unavailable'}. Sensitive fields remain redacted.</p>
          <h5 className="mt-3 text-sm font-medium">Normalized metadata</h5>
          <div className="mt-2"><SafeJsonFields value={evidence.metadata.normalized} /></div>
          <h5 className="mt-4 text-sm font-medium">Sanitized raw metadata</h5>
          <div className="mt-2"><SafeJsonFields value={evidence.metadata.raw} /></div>
          {Object.keys(sourceTags).length > 0 ? (
            <dl className="mt-4 grid gap-2 text-xs sm:grid-cols-2">
              {Object.entries(sourceTags).map(([field, tags]) => (
                <div key={field} className="rounded-lg border border-gray-200 p-2 dark:border-navy-700"><dt className="font-medium">{humanizeForensicLabel(field)}</dt><dd className="mt-1 break-words font-mono text-gray-500">{tags.join(', ')}</dd></div>
              ))}
            </dl>
          ) : null}
        </section>

        <section aria-labelledby="technical-findings-heading">
          <h4 id="technical-findings-heading" className="font-semibold text-gray-900 dark:text-white">Finding groups</h4>
          <h5 className="mt-3 text-sm font-medium">Needs attention</h5>
          {evidence.metadata_inconsistencies.length > 0 ? <ul className="mt-2 space-y-2">{evidence.metadata_inconsistencies.map((finding) => <TechnicalFinding key={`${finding.code}-${finding.title}`} finding={finding} />)}</ul> : <p className="mt-1 text-sm text-gray-500">No metadata conflicts were reported.</p>}
          <h5 className="mt-5 text-sm font-medium">Useful origin details</h5>
          <TechnicalOriginDetails creation={evidence.creation_info} />
          <h5 className="mt-5 text-sm font-medium">Technical encoding details</h5>
          {evidence.compression_indicators.length > 0 ? <ul className="mt-2 space-y-2">{evidence.compression_indicators.map((finding) => <TechnicalFinding key={`${finding.code}-${finding.title}`} finding={finding} />)}</ul> : <p className="mt-1 text-sm text-gray-500">No encoding indicators were reported.</p>}
        </section>

        <section aria-labelledby="technical-credentials-heading">
          <h4 id="technical-credentials-heading" className="font-semibold text-gray-900 dark:text-white">Content Credentials validation</h4>
          <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
            <div><dt className="text-gray-500">Active manifest ID</dt><dd className="break-all font-mono text-xs">{evidence.c2pa.manifest_present ? evidence.c2pa.active_manifest ?? 'Present; identifier unavailable' : 'Not present'}</dd></div>
            <div><dt className="text-gray-500">Signature</dt><dd>{evidence.c2pa.signature_state}</dd></div>
            <div><dt className="text-gray-500">Signer trust</dt><dd>{evidence.c2pa.trust_state}</dd></div>
            <div><dt className="text-gray-500">Asset validation</dt><dd>{evidence.c2pa.validation_state ?? 'unknown'}</dd></div>
            <div><dt className="text-gray-500">Signer summary</dt><dd className="break-words">{evidence.c2pa.signer ?? 'Unavailable'}</dd></div>
            <div><dt className="text-gray-500">Issuer summary</dt><dd className="break-words">{evidence.c2pa.issuer ?? 'Unavailable'}</dd></div>
            <div><dt className="text-gray-500">Claim generator</dt><dd className="break-words">{evidence.c2pa.claim_generator ?? 'Unavailable'}{evidence.c2pa.claim_generator_version ? ` version ${evidence.c2pa.claim_generator_version}` : ''}</dd></div>
            <div><dt className="text-gray-500">Ingredient count</dt><dd>{evidence.c2pa.ingredient_count ?? 0}</dd></div>
            <div><dt className="text-gray-500">Remote references present</dt><dd>{evidence.c2pa.remote_references_present ? 'Yes; not fetched' : 'No'}</dd></div>
            <div><dt className="text-gray-500">Remote fetch performed</dt><dd>{evidence.c2pa.remote_fetch_performed ? 'Yes' : 'No'}</dd></div>
          </dl>
          {evidence.c2pa.provenance ? (
            <div className="mt-4 rounded-lg border border-gray-200 p-3 text-sm dark:border-navy-700">
              <p className="font-medium text-gray-900 dark:text-white">Provenance classification</p>
              <dl className="mt-2 grid gap-2 text-xs sm:grid-cols-2">
                <div><dt className="text-gray-500">Origin state</dt><dd>{evidence.c2pa.provenance.origin_state}</dd></div>
                <div><dt className="text-gray-500">Origin category</dt><dd>{evidence.c2pa.provenance.origin_category}</dd></div>
                <div><dt className="text-gray-500">Basis strength</dt><dd>{evidence.c2pa.provenance.basis_strength}</dd></div>
                <div><dt className="text-gray-500">Source action</dt><dd className="break-words">{evidence.c2pa.provenance.source_action ?? 'Unavailable'}</dd></div>
                <div className="sm:col-span-2"><dt className="text-gray-500">Exact digitalSourceType URI</dt><dd className="break-all font-mono">{evidence.c2pa.provenance.digital_source_type ?? 'Not declared'}</dd></div>
                <div><dt className="text-gray-500">Classification method</dt><dd className="break-words">{evidence.c2pa.provenance.classification_method}</dd></div>
                <div><dt className="text-gray-500">Classification version</dt><dd>{evidence.c2pa.provenance.classification_version}</dd></div>
              </dl>
              {evidence.c2pa.provenance.limitations.length > 0 ? (
                <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-gray-600 dark:text-gray-400">
                  {evidence.c2pa.provenance.limitations.map((limitation, index) => <li key={`${limitation}-${index}`}>{limitation}</li>)}
                </ul>
              ) : null}
            </div>
          ) : null}
          {(evidence.c2pa.assertion_labels ?? []).length > 0 ? (
            <div className="mt-4">
              <h5 className="text-sm font-medium">Assertion labels</h5>
              <ul className="mt-2 space-y-1 text-xs">{evidence.c2pa.assertion_labels?.map((label) => <li key={label}><code className="break-all">{label}</code></li>)}</ul>
            </div>
          ) : null}
          {evidence.c2pa.actions.length > 0 ? (
            <div className="mt-4">
              <h5 className="text-sm font-medium">Ordered active-manifest actions</h5>
              <ol className="mt-2 space-y-2 text-xs">
                {evidence.c2pa.actions.map((action, index) => (
                  <li key={`${action.action}-${index}`} className="rounded-lg border border-gray-200 p-3 dark:border-navy-700">
                    <p><span className="text-gray-500">#{index + 1}</span> <code className="break-all">{action.action}</code></p>
                    <p className="mt-1 break-all"><span className="text-gray-500">digitalSourceType:</span> {action.digital_source_type ?? 'Not declared'}</p>
                    {action.software_agent ? <p className="mt-1 break-words"><span className="text-gray-500">Software agent:</span> {action.software_agent}</p> : null}
                    {action.description ? <p className="mt-1 break-words"><span className="text-gray-500">Description:</span> {action.description}</p> : null}
                  </li>
                ))}
              </ol>
            </div>
          ) : null}
          {(evidence.c2pa.validation_statuses ?? []).length > 0 ? (
            <div className="mt-4">
              <h5 className="text-sm font-medium">Validation codes</h5>
              <ul className="mt-2 space-y-2 text-xs">{evidence.c2pa.validation_statuses?.map((status) => <li key={`${status.code}-${status.summary}`} className="rounded-lg border border-gray-200 p-3 dark:border-navy-700"><code className="break-all">{status.code}</code><p className="mt-1 break-words">{status.summary}</p><p className="mt-1 text-gray-500">{status.category}</p></li>)}</ul>
            </div>
          ) : null}
          {evidence.c2pa.validation_errors.length > 0 ? (
            <div className="mt-4"><h5 className="text-sm font-medium">Validation errors</h5><ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-red-700 dark:text-red-300">{evidence.c2pa.validation_errors.map((error, index) => <li key={`${error}-${index}`} className="break-words">{error}</li>)}</ul></div>
          ) : null}
        </section>

        <section aria-labelledby="technical-matches-heading">
          <h4 id="technical-matches-heading" className="font-semibold text-gray-900 dark:text-white">Similarity measurements</h4>
          {evidence.similarity_matches.length > 0 ? <ul className="mt-2 space-y-2 text-sm">{evidence.similarity_matches.map((match) => <li key={match.analysis_id} className="rounded-lg border border-gray-200 p-3 dark:border-navy-700"><p className="font-medium">{match.filename}</p><p className="mt-1 text-xs">{match.match_type}; {(match.similarity_score * 100).toFixed(1)}%; {match.algorithm}{match.algorithm_version ? ` version ${match.algorithm_version}` : ''}; distance {match.distance ?? 'not applicable'}</p><div className="mt-2"><SafeJsonFields value={match.details} /></div></li>)}</ul> : <p className="mt-1 text-sm text-gray-500">No compatible matches were found.</p>}
        </section>

        {collectionWarnings.length > 0 ? (
          <section aria-labelledby="technical-notes-heading"><h4 id="technical-notes-heading" className="font-semibold text-gray-900 dark:text-white">Collection notes</h4><ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-gray-600 dark:text-gray-400">{collectionWarnings.map((warning, index) => <li key={`${warning}-${index}`}>{warning}</li>)}</ul></section>
        ) : null}
      </div>
    </details>
  );
}
