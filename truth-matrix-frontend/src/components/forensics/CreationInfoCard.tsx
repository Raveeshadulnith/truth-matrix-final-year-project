import { MapPinIcon } from 'lucide-react';
import type { CreationInfo } from '../../api/deepfakeApi';
import { EmptyEvidenceMessage, EvidenceCard, TechnicalDetails } from './ForensicPrimitives';

const CREATION_FIELDS: Array<[keyof CreationInfo, string]> = [
  ['device_make', 'Device make'],
  ['device_model', 'Device model'],
  ['creator', 'Creator'],
  ['created_at', 'Created'],
  ['digitized_at', 'Digitized'],
  ['modified_at', 'Modified'],
];

const SOFTWARE_CATEGORY_LABELS = {
  capture_processing: 'Camera processing',
  editor: 'Editor',
  encoder: 'Encoder',
  ai_generation: 'Named AI generator',
  social_platform: 'Sharing platform',
  metadata_tool: 'Metadata tool',
  unknown: 'Role unknown',
} as const;

export function CreationInfoCard({ creationInfo }: { creationInfo: CreationInfo }) {
  const presentFields = CREATION_FIELDS.filter(([key]) => Boolean(creationInfo[key]));
  const observations = creationInfo.software_observations ?? [];
  const hasInformation = presentFields.length > 0 || creationInfo.software.length > 0;

  return (
    <EvidenceCard
      title="Creation information"
      description="Conservatively normalized embedded creation and workflow details."
    >
      {hasInformation ? (
        <dl className="space-y-3">
          {presentFields.map(([key, label]) => (
            <div key={key} className="grid gap-1 sm:grid-cols-[8rem_minmax(0,1fr)]">
              <dt className="text-sm text-gray-500 dark:text-gray-400">{label}</dt>
              <dd className="break-words text-sm font-medium text-gray-900 dark:text-white">
                {String(creationInfo[key])}
              </dd>
            </div>
          ))}
          {observations.length > 0 ? (
            <div className="grid gap-1 sm:grid-cols-[8rem_minmax(0,1fr)]">
              <dt className="text-sm text-gray-500 dark:text-gray-400">Workflow software</dt>
              <dd className="space-y-2">
                {observations.map((observation) => (
                  <div
                    key={`${observation.name}-${observation.category}`}
                    className="rounded-md bg-gray-50 px-3 py-2 dark:bg-navy-800"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="break-words text-sm font-medium text-gray-900 dark:text-white">
                        {observation.name}
                      </span>
                      <span className="rounded-full bg-gray-200 px-2 py-0.5 text-xs text-gray-700 dark:bg-navy-700 dark:text-gray-300">
                        {SOFTWARE_CATEGORY_LABELS[observation.category]}
                      </span>
                    </div>
                    <p className="mt-1 text-xs leading-relaxed text-gray-600 dark:text-gray-400">
                      {observation.user_description}
                    </p>
                  </div>
                ))}
              </dd>
            </div>
          ) : creationInfo.software.length > 0 ? (
            <div className="grid gap-1 sm:grid-cols-[8rem_minmax(0,1fr)]">
              <dt className="text-sm text-gray-500 dark:text-gray-400">Workflow software</dt>
              <dd className="flex flex-wrap gap-1.5">
                {creationInfo.software.map((software) => (
                  <span
                    key={software}
                    className="break-words rounded-md bg-gray-100 px-2 py-1 text-xs text-gray-800 dark:bg-navy-700 dark:text-gray-200"
                  >
                    {software} · role unavailable in this older result
                  </span>
                ))}
              </dd>
            </div>
          ) : null}
        </dl>
      ) : (
        <EmptyEvidenceMessage>
          No embedded creation details were available. This is not evidence of manipulation.
        </EmptyEvidenceMessage>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-700 dark:bg-navy-700 dark:text-gray-300">
          <MapPinIcon className="h-3.5 w-3.5" />
          Location {creationInfo.location_present ? 'present (coordinates hidden)' : 'not present'}
        </span>
        <span className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-700 dark:bg-navy-700 dark:text-gray-300">
          Timezone {creationInfo.timezone_present ? 'present' : 'not present'}
        </span>
      </div>

      {Object.keys(creationInfo.source_tags).length > 0 ? (
        <TechnicalDetails label="Source tags">
          <dl className="space-y-2 text-sm">
            {Object.entries(creationInfo.source_tags).map(([field, tags]) => (
              <div key={field} className="grid gap-1 sm:grid-cols-[8rem_minmax(0,1fr)]">
                <dt className="text-gray-500 dark:text-gray-400">{field.replace(/_/g, ' ')}</dt>
                <dd className="break-words font-mono text-xs text-gray-800 dark:text-gray-200">
                  {tags.join(', ')}
                </dd>
              </div>
            ))}
          </dl>
        </TechnicalDetails>
      ) : null}
    </EvidenceCard>
  );
}
