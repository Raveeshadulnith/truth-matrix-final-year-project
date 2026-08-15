import { useEffect, useState, type ReactNode } from 'react';
import { CheckIcon, Clock3Icon, CopyIcon, EyeIcon, EyeOffIcon, MapPinIcon, SmartphoneIcon, WorkflowIcon } from 'lucide-react';
import type {
  CreationInfo,
  MetadataEvidence,
  PreciseLocationResponse,
  SoftwareCategory,
} from '../../api/deepfakeApi';
import { ApiError, getPreciseLocation } from '../../api/deepfakeApi';
import { useAuthStore } from '../../store/authStore';

const SOFTWARE_LABELS: Record<SoftwareCategory, string> = {
  capture_processing: 'Camera processing',
  editor: 'Editing software',
  encoder: 'Encoder/export tool',
  ai_generation: 'AI-generation tool',
  social_platform: 'Sharing platform',
  metadata_tool: 'Metadata tool',
  unknown: 'Unknown workflow software',
};

function formatEmbeddedDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(parsed);
}

function DetailRow({
  icon: Icon,
  label,
  children,
}: {
  icon: typeof SmartphoneIcon;
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="grid min-w-0 gap-1 py-3 first:pt-0 last:pb-0 sm:grid-cols-[10rem_minmax(0,1fr)]">
      <dt className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
        <Icon className="h-4 w-4 flex-none" aria-hidden="true" />
        {label}
      </dt>
      <dd className="break-words text-sm font-medium text-gray-900 dark:text-white">
        {children}
      </dd>
    </div>
  );
}

export function OriginHistoryCard({
  creationInfo,
  analysisId,
  canRevealPreciseLocation = false,
}: {
  creationInfo: CreationInfo;
  metadata: MetadataEvidence;
  analysisId?: string;
  canRevealPreciseLocation?: boolean;
}) {
  const accessToken = useAuthStore((state) => state.accessToken);
  const refreshSession = useAuthStore((state) => state.refreshSession);
  const [showPrivacyNotice, setShowPrivacyNotice] = useState(false);
  const [location, setLocation] = useState<PreciseLocationResponse | null>(null);
  const [locationError, setLocationError] = useState<string | null>(null);
  const [isLocationLoading, setIsLocationLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const observations = creationInfo.software_observations ?? [];
  const device = [creationInfo.device_make, creationInfo.device_model]
    .filter(Boolean)
    .join(' ');
  const hasUsefulDetails = Boolean(device || creationInfo.created_at || observations.length > 0 || creationInfo.location_present);
  const mayReveal = creationInfo.location_present && canRevealPreciseLocation && Boolean(analysisId);
  const coordinates = location?.status === 'available' && typeof location.latitude === 'number' && typeof location.longitude === 'number'
    ? `${location.latitude.toFixed(6)}, ${location.longitude.toFixed(6)}`
    : null;

  useEffect(() => {
    setShowPrivacyNotice(false);
    setLocation(null);
    setLocationError(null);
    setCopied(false);
    return () => {
      setLocation(null);
    };
  }, [analysisId]);

  const revealLocation = async () => {
    if (!analysisId || isLocationLoading) return;
    setIsLocationLoading(true);
    setLocationError(null);
    try {
      let token = accessToken || (await refreshSession());
      if (!token) throw new Error('Please sign in again.');
      try {
        setLocation(await getPreciseLocation(token, analysisId));
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          token = await refreshSession();
          if (token) {
            setLocation(await getPreciseLocation(token, analysisId));
            return;
          }
        }
        throw error;
      }
    } catch {
      setLocationError('Precise location could not be revealed.');
    } finally {
      setIsLocationLoading(false);
      setShowPrivacyNotice(false);
    }
  };

  const copyCoordinates = async () => {
    if (!coordinates) return;
    try {
      await navigator.clipboard.writeText(coordinates);
      setCopied(true);
    } catch {
      setLocationError('Coordinates could not be copied.');
    }
  };

  return (
    <section
      aria-labelledby="origin-history-heading"
      className="min-w-0 rounded-2xl border border-gray-200 bg-white p-4 shadow-sm dark:border-navy-700 dark:bg-navy-800 sm:p-5"
    >
      <h3 id="origin-history-heading" className="font-semibold text-gray-900 dark:text-white">
        File origin details
      </h3>
      {!hasUsefulDetails ? <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">No useful origin details were embedded.</p> : null}

      <dl className="mt-3 divide-y divide-gray-100 dark:divide-navy-700">
        {device ? <DetailRow icon={SmartphoneIcon} label="Device">{device}</DetailRow> : null}
        <DetailRow icon={Clock3Icon} label="Captured">
          <span>{creationInfo.created_at ? formatEmbeddedDate(creationInfo.created_at) : 'Capture time was not embedded'}</span>
          {creationInfo.created_at && !creationInfo.timezone_present ? (
            <span className="mt-1 block text-xs font-normal text-gray-500 dark:text-gray-400">
              No timezone was embedded; the time is shown as recorded.
            </span>
          ) : null}
        </DetailRow>

        {observations.map((observation) => (
          <DetailRow
            key={`${observation.category}-${observation.name}`}
            icon={WorkflowIcon}
            label={SOFTWARE_LABELS[observation.category]}
          >
            {observation.name}
          </DetailRow>
        ))}

        {creationInfo.location_present ? (
          <DetailRow icon={MapPinIcon} label="Location">
            <div>
              <span>{coordinates ?? 'Present'}</span>
              {location?.source && coordinates ? <span className="mt-1 block text-xs font-normal text-gray-500 dark:text-gray-400">{location.source}</span> : null}
              {mayReveal && !location && !showPrivacyNotice ? (
                <button type="button" onClick={() => setShowPrivacyNotice(true)} className="mt-2 inline-flex items-center gap-1.5 rounded-lg border border-violet-300 px-2.5 py-1.5 text-xs font-semibold text-violet-700 hover:bg-violet-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 dark:border-violet-700 dark:text-violet-200 dark:hover:bg-violet-950/30">
                  <EyeIcon className="h-3.5 w-3.5" aria-hidden="true" />Reveal precise location
                </button>
              ) : null}
              {showPrivacyNotice && !coordinates ? (
                <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50 p-2.5 text-xs font-normal text-amber-950 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-100">
                  <p>This file contains precise location information. Reveal it only in a private setting.</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <button type="button" onClick={() => void revealLocation()} disabled={isLocationLoading} className="rounded-lg bg-violet-700 px-2.5 py-1.5 font-semibold text-white disabled:opacity-60">{isLocationLoading ? 'Revealing...' : 'Reveal location now'}</button>
                    <button type="button" onClick={() => setShowPrivacyNotice(false)} className="rounded-lg border border-current/20 px-2.5 py-1.5 font-semibold">Cancel</button>
                  </div>
                </div>
              ) : null}
              {coordinates ? (
                <span className="mt-2 flex flex-wrap gap-2">
                  <button type="button" onClick={() => void copyCoordinates()} className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 px-2.5 py-1.5 text-xs font-semibold dark:border-navy-600">
                    {copied ? <CheckIcon className="h-3.5 w-3.5" aria-hidden="true" /> : <CopyIcon className="h-3.5 w-3.5" aria-hidden="true" />}{copied ? 'Copied' : 'Copy coordinates'}
                  </button>
                  <button type="button" onClick={() => { setLocation(null); setCopied(false); }} className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 px-2.5 py-1.5 text-xs font-semibold dark:border-navy-600">
                    <EyeOffIcon className="h-3.5 w-3.5" aria-hidden="true" />Hide coordinates
                  </button>
                </span>
              ) : null}
              {location && location.status !== 'available' ? <span role="status" className="mt-2 block text-xs font-normal text-gray-500 dark:text-gray-400">Precise location is {location.status.replaceAll('_', ' ')} for this saved analysis.</span> : null}
              {locationError ? <span role="alert" className="mt-2 block text-xs font-normal text-red-700 dark:text-red-300">{locationError}</span> : null}
            </div>
          </DetailRow>
        ) : null}
      </dl>
    </section>
  );
}
