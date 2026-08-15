import {
  AlertTriangleIcon,
  BadgeCheckIcon,
  CircleHelpIcon,
  InfoIcon,
  ShieldCheckIcon,
} from 'lucide-react';
import type {
  C2paEvidence,
  C2paOriginCategory,
  C2paOriginState,
} from '../../api/deepfakeApi';

type PresentationTone = 'verified' | 'untrusted' | 'invalid' | 'neutral';

interface CredentialPresentation {
  headline: string;
  message?: string;
  originLabel?: string;
  tone: PresentationTone;
}

const CARD_STYLES: Record<PresentationTone, string> = {
  verified:
    'border-violet-200 bg-gradient-to-br from-blue-50 to-violet-50 dark:border-violet-800 dark:from-blue-950/35 dark:to-violet-950/30',
  untrusted:
    'border-amber-300 bg-amber-50/80 dark:border-amber-800 dark:bg-amber-950/25',
  invalid:
    'border-red-300 bg-red-50/80 dark:border-red-800 dark:bg-red-950/25',
  neutral:
    'border-gray-200 bg-gray-50/80 dark:border-navy-700 dark:bg-navy-800',
};

const ICON_STYLES: Record<PresentationTone, string> = {
  verified: 'bg-violet-100 text-violet-700 dark:bg-violet-900/50 dark:text-violet-300',
  untrusted: 'bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-300',
  invalid: 'bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300',
  neutral: 'bg-gray-200 text-gray-600 dark:bg-navy-700 dark:text-gray-300',
};

const CATEGORY_LABELS: Partial<Record<C2paOriginCategory, string>> = {
  ai_generated: 'Created using Generative AI',
  ai_edited: 'Edited using Generative AI',
  camera_capture: 'Captured with a camera or recording device',
  screen_capture: 'Created as a screen capture',
  human_edited: 'Edited by a person using non-generative tools',
  digital_creation: 'Created digitally using non-generative tools',
  mixed_or_synthetic: 'Composite containing synthetic elements',
};

const STATE_HEADLINES: Partial<Record<C2paOriginState, string>> = {
  verified_ai_generated: 'Verified AI-generated origin',
  declared_ai_generated_untrusted:
    'AI-generated origin declared; signer trust not established',
  verified_ai_edited: 'Verified AI-assisted editing',
  declared_ai_edited_untrusted:
    'AI-assisted editing declared; signer trust not established',
  verified_camera_capture: 'Verified camera capture',
  verified_screen_capture: 'Verified screen capture',
  verified_human_edited: 'Verified human editing history',
  invalid_credential: 'Invalid Content Credentials',
  verification_unavailable: 'Content Credentials verification unavailable',
  no_origin_declaration: 'Valid Content Credentials; origin type not specified',
};

function credentialPresentation(c2pa: C2paEvidence): CredentialPresentation {
  const provenance = c2pa.provenance;
  if (
    c2pa.status === 'unsupported' ||
    c2pa.status === 'unavailable' ||
    c2pa.status === 'error' ||
    provenance?.origin_state === 'verification_unavailable'
  ) {
    return {
      headline: 'Content Credentials verification unavailable',
      message: 'The credential checker could not run for this file.',
      tone: 'neutral',
    };
  }
  if (!c2pa.manifest_present || c2pa.status === 'not_present') {
    return {
      headline: 'Content Credentials not attached - common and neutral',
      tone: 'neutral',
    };
  }
  if (
    c2pa.signature_state === 'invalid' ||
    c2pa.validation_state === 'invalid' ||
    provenance?.origin_state === 'invalid_credential'
  ) {
    return {
      headline: 'Invalid Content Credentials',
      message: 'The credential signature or the signed file failed validation.',
      tone: 'invalid',
    };
  }

  const originState = provenance?.origin_state;
  const originLabel = provenance
    ? CATEGORY_LABELS[provenance.origin_category]
    : undefined;
  const trustNotEstablished =
    provenance?.basis_strength === 'valid_untrusted' ||
    (c2pa.signature_state === 'valid' && c2pa.trust_state !== 'trusted');
  const tone: PresentationTone = trustNotEstablished ? 'untrusted' : 'verified';

  if (originState === 'verified_digital_creation') {
    return {
      headline: 'Valid Content Credentials; origin type not specified',
      originLabel,
      tone,
    };
  }
  if (originState === 'verified_mixed_or_synthetic') {
    return {
      headline: 'Valid Content Credentials; origin type not specified',
      originLabel,
      tone,
    };
  }

  return {
    headline:
      (originState && STATE_HEADLINES[originState]) ??
      'Valid Content Credentials; origin type not specified',
    originLabel,
    tone,
  };
}

function displayState(value: string): string {
  const labels: Record<string, string> = {
    valid: 'Valid signature',
    invalid: 'Invalid signature',
    trusted: 'Trusted',
    untrusted: 'Not established',
    not_checked: 'Not checked',
    not_applicable: 'Not applicable',
    unknown: 'Unknown',
  };
  return labels[value] ?? value.replaceAll('_', ' ');
}

function StateIcon({ tone }: { tone: PresentationTone }) {
  if (tone === 'verified') return <BadgeCheckIcon className="h-6 w-6" aria-hidden="true" />;
  if (tone === 'untrusted') return <CircleHelpIcon className="h-6 w-6" aria-hidden="true" />;
  if (tone === 'invalid') return <AlertTriangleIcon className="h-6 w-6" aria-hidden="true" />;
  return <InfoIcon className="h-6 w-6" aria-hidden="true" />;
}

function CredentialFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-xl border border-white/80 bg-white/75 p-3 dark:border-navy-700 dark:bg-navy-900/45">
      <dt className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
        {label}
      </dt>
      <dd className="mt-1 break-words text-sm font-semibold text-gray-900 dark:text-white">
        {value}
      </dd>
    </div>
  );
}

export function ProvenanceCredentialsCard({ c2pa }: { c2pa: C2paEvidence }) {
  const presentation = credentialPresentation(c2pa);
  const provenance = c2pa.provenance;
  const showCredentialFacts = c2pa.manifest_present;
  const provider = provenance?.provider ?? provenance?.claim_generator ?? c2pa.claim_generator;
  const isAiEdited = provenance?.origin_category === 'ai_edited';

  return (
    <section
      id="content-credentials"
      aria-label="Provenance and Content Credentials"
      aria-labelledby="content-credentials-heading"
      className={`min-w-0 rounded-2xl border p-4 shadow-sm sm:p-5 ${CARD_STYLES[presentation.tone]}`}
      data-provenance-tone={presentation.tone}
    >
      <div className="flex min-w-0 items-start gap-3">
        <div className={`flex h-11 w-11 flex-none items-center justify-center rounded-xl ${ICON_STYLES[presentation.tone]}`}>
          <StateIcon tone={presentation.tone} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-gray-300">
            <ShieldCheckIcon className="h-4 w-4" aria-hidden="true" />
            Content Credentials
          </div>
          <h3 id="content-credentials-heading" className="mt-1 break-words text-lg font-bold text-gray-950 dark:text-white sm:text-xl">
            {presentation.headline}
          </h3>
          {presentation.message ? <p className="mt-2 max-w-3xl break-words text-sm text-gray-700 dark:text-gray-300">{presentation.message}</p> : null}
          {isAiEdited ? (
            <p className="mt-2 text-sm font-medium text-violet-900 dark:text-violet-200">
              Generative AI was declared for part of the workflow, not necessarily the whole file.
            </p>
          ) : null}
        </div>
      </div>

      {showCredentialFacts ? (
        <dl className="mt-4 grid min-w-0 gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {presentation.originLabel ? <CredentialFact label="Origin" value={presentation.originLabel} /> : null}
          {provider ? <CredentialFact label="Provider" value={provider} /> : null}
          <CredentialFact label="Credential" value={displayState(c2pa.signature_state)} />
          <CredentialFact label="Signer trust" value={displayState(c2pa.trust_state)} />
        </dl>
      ) : null}

      {showCredentialFacts ? <p className="mt-3 text-xs text-gray-600 dark:text-gray-300">Verifies the declared file history, not whether the depicted claim is true.</p> : null}
    </section>
  );
}
