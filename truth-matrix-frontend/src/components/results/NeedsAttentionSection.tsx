import { AlertTriangleIcon, FileWarningIcon, WorkflowIcon } from 'lucide-react';
import type {
  ForensicEvidence,
  ForensicFinding,
  ForensicScoreContribution,
} from '../../api/deepfakeApi';

interface ExplanationItem {
  key: string;
  title: string;
  found: string;
  why: string;
  limitation: string;
}

function contributionItems(evidence: ForensicEvidence): ExplanationItem[] {
  const contributions = evidence.assessment?.score_contributions.filter((item) => item.points > 0) ?? [];
  const findings = [...evidence.metadata_inconsistencies, ...evidence.compression_indicators];
  const byCode = new Map<string, ForensicFinding>();
  findings.forEach((finding) => byCode.set(finding.code, finding));

  const unique = new Map<string, ForensicScoreContribution>();
  contributions.forEach((contribution) => {
    if (!unique.has(contribution.finding_code)) unique.set(contribution.finding_code, contribution);
  });

  return [...unique.values()].map((contribution: ForensicScoreContribution) => {
    const finding = byCode.get(contribution.finding_code);
    return {
      key: contribution.finding_code,
      title: finding?.title ?? contribution.finding_code.replace(/[._]/g, ' '),
      found: finding?.explanation ?? contribution.reason,
      why: contribution.reason,
      limitation: contribution.limitations[0] ?? finding?.limitations[0] ?? 'This signal should be reviewed with the model result and other evidence; it is not proof by itself.',
    };
  });
}

function verifiedOriginItems(evidence: ForensicEvidence): ExplanationItem[] {
  const provenance = evidence.c2pa.provenance;
  if (!provenance) return [];
  const explainableStates = new Set([
    'verified_ai_generated',
    'declared_ai_generated_untrusted',
    'verified_ai_edited',
    'declared_ai_edited_untrusted',
    'invalid_credential',
  ]);
  if (!explainableStates.has(provenance.origin_state)) return [];
  return [{
    key: `provenance-${provenance.origin_state}`,
    title: 'Content Credentials origin declaration',
    found: 'A signed origin or workflow declaration is available in the Provenance and Content Credentials card above.',
    why: provenance.origin_category === 'ai_generated'
      ? 'The signed workflow declares a generative-AI origin and is useful origin evidence.'
      : provenance.origin_category === 'ai_edited'
        ? 'The signed workflow declares that generative AI was used during part of the editing process.'
        : 'The credential could not be validated reliably and deserves review.',
    limitation: provenance.limitations[0] ?? 'Content Credentials describe a signed workflow; they do not prove that the depicted event or claim is true.',
  }];
}

function workflowItems(evidence: ForensicEvidence): ExplanationItem[] {
  const relevant = (evidence.creation_info.software_observations ?? []).filter(
    (item) => item.category === 'editor' || item.category === 'ai_generation',
  );
  return relevant.map((item) => ({
    key: `workflow-${item.category}-${item.name}`,
    title: item.category === 'ai_generation' ? 'AI-generation tool identified' : 'Editing software identified',
    found: `${item.name} was explicitly named in the collected metadata.`,
    why: item.user_description,
    limitation: item.category === 'editor'
      ? 'Editing software can be used for ordinary, non-deceptive changes and does not prove manipulation by itself.'
      : 'A software name is workflow evidence; signed Content Credentials provide stronger provenance when available.',
  }));
}

function availabilityItems(evidence: ForensicEvidence): ExplanationItem[] {
  if (evidence.status === 'complete') return [];
  return [{
    key: `availability-${evidence.status}`,
    title: evidence.status === 'error' ? 'Forensic collection failed' : 'Some forensic checks were unavailable',
    found: evidence.warnings[0] ?? 'Not every applicable extractor completed for this analysis.',
    why: 'Coverage affects how much file-level evidence can be reviewed, but it does not increase the concern score by itself.',
    limitation: 'Unavailable evidence is unknown, not evidence that the media was manipulated.',
  }];
}

function ExplanationGroup({
  title,
  icon: Icon,
  items,
}: {
  title: string;
  icon: typeof AlertTriangleIcon;
  items: ExplanationItem[];
}) {
  if (items.length === 0) return null;
  return (
    <section className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-navy-700 dark:bg-navy-800 sm:p-5">
      <h3 className="flex items-center gap-2 font-semibold text-gray-900 dark:text-white">
        <Icon className="h-5 w-5 text-amber-600 dark:text-amber-300" aria-hidden="true" />
        {title}
      </h3>
      <ul className="mt-4 space-y-4">
        {items.map((item) => (
          <li key={item.key} className="rounded-xl border border-gray-200 bg-gray-50 p-3 dark:border-navy-700 dark:bg-navy-900/50">
            <h4 className="font-semibold text-gray-900 dark:text-white">{item.title}</h4>
            <dl className="mt-2 space-y-2 text-sm leading-relaxed">
              <div><dt className="font-medium text-gray-700 dark:text-gray-300">What was found</dt><dd className="text-gray-600 dark:text-gray-400">{item.found}</dd></div>
              <div><dt className="font-medium text-gray-700 dark:text-gray-300">Why it matters</dt><dd className="text-gray-600 dark:text-gray-400">{item.why}</dd></div>
              <div><dt className="font-medium text-gray-700 dark:text-gray-300">What it cannot prove</dt><dd className="text-gray-600 dark:text-gray-400">{item.limitation}</dd></div>
            </dl>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function NeedsAttentionSection({ evidence }: { evidence?: ForensicEvidence }) {
  if (!evidence) return null;
  const origin = verifiedOriginItems(evidence);
  const conflicts = contributionItems(evidence);
  const workflow = [...workflowItems(evidence), ...availabilityItems(evidence)];
  if (origin.length + conflicts.length + workflow.length === 0) return null;

  return (
    <section data-result-section="needs-attention" aria-labelledby="needs-attention-heading">
      <h2 id="needs-attention-heading" className="text-2xl font-bold text-gray-900 dark:text-white">Needs attention</h2>
      <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">Only evidence that benefits from explanation is shown here. Routine encoding measurements remain in Technical details.</p>
      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <ExplanationGroup title="Verified origin" icon={AlertTriangleIcon} items={origin} />
        <ExplanationGroup title="File conflicts" icon={FileWarningIcon} items={conflicts} />
        <ExplanationGroup title="Workflow and limitations" icon={WorkflowIcon} items={workflow} />
      </div>
    </section>
  );
}
