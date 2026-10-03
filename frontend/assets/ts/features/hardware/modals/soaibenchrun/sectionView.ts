/* SoAI - SoAI Bench run section presentation [frontend/assets/ts/features/hardware/modals/soaibenchrun/sectionView.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderModalFooterActionButton } from '@core/modals/footerButtons.ts';
import { formatPositiveEpochMsSecondWithFallback } from '@core/primitives/dateTime.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import { HARDWARE_SOAIBENCH_RUN_AGAIN_ACTION, HARDWARE_SOAIBENCH_RUN_COPY_ACTION, HARDWARE_SOAIBENCH_RUN_DOWNLOAD_ACTION, HARDWARE_SOAIBENCH_RUN_HISTORY_ACTION, HARDWARE_SOAIBENCH_RUN_PUBLISH_ACTION, HARDWARE_SOAIBENCH_RUN_RECOVER_ACTION, HARDWARE_SOAIBENCH_RUN_RETRY_ACTION, HARDWARE_SOAIBENCH_RUN_STOP_ACTION } from '@features/hardware/modals/soaibenchrun/constants.ts';
import type { SoAIBenchRunEntry, SoAIBenchRunPhase } from '@features/hardware/modals/soaibenchrun/types.ts';
import { renderGpuLabel, summaryBadgeForRun, type SummaryBadge } from '@features/hardware/modals/soaibenchrun/view.ts';
import { resolveSoAIBenchStatusLabel } from '@features/hardware/soaibenchLabels.ts';
import { getSoAIBenchNotAvailableLabel } from '@features/hardware/soaibenchMetricFormatting.ts';

type SoAIBenchSectionActionVariant = 'neutral' | 'primary' | 'accent' | 'danger' | 'violet';

interface SoAIBenchSectionAction {
    action: string;
    label: string;
    ariaLabel: string;
    variant: SoAIBenchSectionActionVariant;
    disabled: boolean;
}

interface SoAIBenchSectionActionInput {
    entry: SoAIBenchRunEntry;
    phase: SoAIBenchRunPhase;
    historyAvailable: boolean;
    publishing: boolean;
}

const renderSoAIBenchSection = (entry: SoAIBenchRunEntry): TrustedHtml => {
    const titleId = `${entry.sectionId}-title`;
    return uiHtml`<section class="hardware-soaibench-run-entry" data-soaibench-section="${uiAttr(entry.sectionId)}" aria-labelledby="${uiAttr(titleId)}"><div class="hardware-soaibench-run-summary"><div class="hardware-soaibench-run-heading"><h3 class="hardware-soaibench-run-gpu" id="${uiAttr(titleId)}" tabindex="-1" data-soaibench-slot="heading">${renderGpuLabel(entry.request)}</h3><span class="hardware-soaibench-run-started" data-soaibench-slot="started"></span></div><span class="ui-status-badge" data-soaibench-slot="badge"></span></div><div class="hardware-soaibench-run-content" data-soaibench-slot="content"></div><p class="hardware-soaibench-run-status inline-loading-status u-hidden" role="status" data-soaibench-slot="status"></p><div class="hardware-soaibench-run-actions" data-soaibench-slot="actions"></div></section>`;
};

const resolveSectionBadge = (entry: SoAIBenchRunEntry, phase: SoAIBenchRunPhase): SummaryBadge => {
    if (phase === 'starting') {
        return { label: i18n.t('hardware.modals.soaibenchRun.states.starting'), className: 'status-orange' };
    }
    if (phase === 'stopping') {
        return { label: i18n.t('hardware.modals.soaibenchRun.stopping'), className: 'status-orange' };
    }
    if (phase === 'unresolved') {
        return { label: i18n.t('hardware.modals.soaibenchRun.states.unresolved'), className: 'status-grey' };
    }
    if (phase === 'rejected') {
        return { label: i18n.t('hardware.modals.soaibenchRun.states.rejected'), className: 'status-red' };
    }
    return entry.run === null ? { label: resolveSoAIBenchStatusLabel('running'), className: 'status-orange' } : summaryBadgeForRun(entry.run);
};

const resolveSectionStartedLabel = (entry: SoAIBenchRunEntry): string => {
    return i18n.t('hardware.modals.soaibenchRun.startedAt', { time: formatPositiveEpochMsSecondWithFallback(entry.run?.startedAtMs ?? entry.createdAtMs, getSoAIBenchNotAvailableLabel()) });
};

const sectionAction = (action: string, label: string, ariaLabel: string, variant: SoAIBenchSectionActionVariant, disabled = false): SoAIBenchSectionAction => ({ action, label, ariaLabel, variant, disabled });

const resolvePhaseActions = (entry: SoAIBenchRunEntry, phase: SoAIBenchRunPhase): SoAIBenchSectionAction[] => {
    switch (phase) {
        case 'running':
            return [sectionAction(HARDWARE_SOAIBENCH_RUN_STOP_ACTION, i18n.t('hardware.modals.soaibenchRun.stop'), i18n.t('hardware.modals.soaibenchRun.ariaLabels.stop'), 'danger')];
        case 'stopping':
            return [sectionAction(HARDWARE_SOAIBENCH_RUN_STOP_ACTION, i18n.t('hardware.modals.soaibenchRun.stopping'), i18n.t('hardware.modals.soaibenchRun.ariaLabels.stopping'), 'danger', true)];
        case 'unresolved':
            return [sectionAction(HARDWARE_SOAIBENCH_RUN_RECOVER_ACTION, i18n.t('hardware.modals.soaibenchRun.retry'), i18n.t('hardware.modals.soaibenchRun.ariaLabels.recover'), 'neutral', entry.recovering)];
        case 'rejected':
            return [sectionAction(HARDWARE_SOAIBENCH_RUN_RETRY_ACTION, i18n.t('hardware.modals.soaibenchRun.retry'), i18n.t('hardware.modals.soaibenchRun.ariaLabels.retry'), 'neutral')];
        case 'terminal': {
            const actions = [sectionAction(HARDWARE_SOAIBENCH_RUN_COPY_ACTION, i18n.t('hardware.modals.soaibenchRun.copy'), i18n.t('hardware.modals.soaibenchRun.ariaLabels.copy'), 'primary'), sectionAction(HARDWARE_SOAIBENCH_RUN_DOWNLOAD_ACTION, i18n.t('hardware.modals.soaibenchRun.download'), i18n.t('hardware.modals.soaibenchRun.ariaLabels.download'), 'accent')];
            if (entry.run?.publicationEligible === true) {
                actions.push(sectionAction(HARDWARE_SOAIBENCH_RUN_PUBLISH_ACTION, i18n.t('hardware.soaibenchPublication.action'), i18n.t('hardware.soaibenchPublication.ariaLabel'), 'violet'));
            }
            actions.push(sectionAction(HARDWARE_SOAIBENCH_RUN_AGAIN_ACTION, i18n.t('hardware.modals.soaibenchRun.runAgain'), i18n.t('hardware.modals.soaibenchRun.ariaLabels.runAgain'), 'neutral'));
            return actions;
        }
        case 'starting':
            return [];
    }
};

const resolveSectionActions = (input: SoAIBenchSectionActionInput): SoAIBenchSectionAction[] => {
    const history = input.historyAvailable ? [sectionAction(HARDWARE_SOAIBENCH_RUN_HISTORY_ACTION, i18n.t('hardware.modals.soaibenchRun.history'), i18n.t('hardware.modals.soaibenchRun.ariaLabels.history'), 'neutral')] : [];
    const actions = [...history, ...resolvePhaseActions(input.entry, input.phase)];
    return input.publishing ? actions.map((action) => ({ ...action, disabled: true })) : actions;
};

const renderSectionActionButton = (entry: SoAIBenchRunEntry, action: SoAIBenchSectionAction): TrustedHtml => {
    return renderModalFooterActionButton({ text: action.label, ariaLabel: action.ariaLabel, action: action.action, variant: action.variant, disabled: action.disabled, attributes: { 'data-soaibench-section': entry.sectionId } });
};

export { renderSectionActionButton, renderSoAIBenchSection, resolveSectionActions, resolveSectionBadge, resolveSectionStartedLabel };
export type { SoAIBenchSectionAction };
