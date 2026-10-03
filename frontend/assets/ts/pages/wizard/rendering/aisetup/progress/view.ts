/* SoAI - Wizard AI setup progress and completion view [frontend/assets/ts/pages/wizard/rendering/aisetup/progress/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { OperationProgressData } from '@core/operationprogress/types.ts';
import type { AiSetupCompletionView } from '@pages/wizard/contracts/aisetup/types.ts';
import { renderAiSetupHeading, renderIcon } from '@pages/wizard/rendering/aisetup/view.ts';
import type { AiSetupProgressSummary, AiSetupRow, AiSetupRowAction, AiSetupRowFailure } from '@pages/wizard/services/aisetup/progress/mappers.ts';
import type { WizardViewContext } from '@pages/wizard/types.ts';

const readFailureMessage = (failure: AiSetupRowFailure): string => {
    switch (failure) {
        case 'install_failed':
            return i18n.t('wizard.aiSetup.progress.error.installFailed');
        case 'download_failed':
            return i18n.t('wizard.aiSetup.progress.error.downloadFailed');
        case 'no_disk_space':
            return i18n.t('wizard.aiSetup.progress.error.noDiskSpace');
        case 'empty':
            return i18n.t('wizard.aiSetup.progress.error.empty');
        case 'load_error':
            return i18n.t('wizard.aiSetup.progress.error.loadError');
        case 'timeout':
            return i18n.t('wizard.aiSetup.progress.error.timeout');
        case 'disconnected':
        case 'cancelled':
            return i18n.t('wizard.aiSetup.progress.error.disconnected');
    }
};

const readActionLabel = (action: AiSetupRowAction): string => {
    switch (action) {
        case 'retry':
            return i18n.t('wizard.aiSetup.progress.retry');
        case 'retry_installation':
            return i18n.t('wizard.aiSetup.progress.retryInstallation');
        case 'skip':
            return i18n.t('wizard.aiSetup.progress.skipItem');
        case 'test_again':
            return i18n.t('wizard.aiSetup.progress.testAgain');
        case 'check_again':
            return i18n.t('wizard.aiSetup.progress.checkAgain');
        case 'send_test':
            return i18n.t('wizard.aiSetup.progress.sendTest');
    }
};

const indeterminate = (message: string, state: NonNullable<OperationProgressData['state']>, details: string): OperationProgressData => ({ message, state, details, indeterminate: true, cancelable: false, badge: '' });

const describeAiSetupRow = (row: AiSetupRow): OperationProgressData => {
    const engine = { engine: row.engineLabel };
    const model = { model: row.label };
    switch (row.phase) {
        case 'checking':
            return indeterminate(i18n.t('wizard.aiSetup.progress.checkingStatus'), 'pending', row.label);
        case 'installing':
            return row.progress?.progress === undefined ? { ...indeterminate(i18n.t('wizard.aiSetup.progress.installing', engine), 'downloading', row.progress?.details ?? ''), cancelable: true } : { ...row.progress, message: i18n.t('wizard.aiSetup.progress.installing', engine), state: 'downloading', indeterminate: false, cancelable: true, badge: '' };
        case 'installed':
            return { message: row.label, state: 'success', progress: 100, indeterminate: false, cancelable: false, details: '', badge: i18n.t('wizard.aiSetup.connect.local.status.installed') };
        case 'waiting':
            return indeterminate(i18n.t('wizard.aiSetup.progress.waitingForEngine', engine), 'pending', row.label);
        case 'blocked':
            return { message: i18n.t('wizard.aiSetup.progress.blocked', engine), state: 'error', progress: 0, indeterminate: false, cancelable: false, details: row.label, badge: '' };
        case 'starting':
            return indeterminate(i18n.t('wizard.aiSetup.progress.downloading', model), 'downloading', '');
        case 'downloading':
            return row.progress?.progress === undefined ? { ...indeterminate(i18n.t('wizard.aiSetup.progress.downloading', model), 'downloading', row.progress?.details ?? ''), cancelable: true } : { ...row.progress, message: i18n.t('wizard.aiSetup.progress.downloading', model), state: 'downloading', indeterminate: false, cancelable: true, badge: '' };
        case 'discovering':
            return indeterminate(i18n.t('wizard.aiSetup.progress.discovering', model), 'info', '');
        case 'configuring':
            return indeterminate(i18n.t('wizard.aiSetup.progress.configuring'), 'info', row.label);
        case 'testing':
            return indeterminate(i18n.t('wizard.aiSetup.progress.testing'), 'info', row.label);
        case 'ready':
            return { message: i18n.t('wizard.aiSetup.progress.ready', model), state: 'success', progress: 100, indeterminate: false, cancelable: false, details: '', badge: '' };
        case 'stale':
            return { message: row.label, state: 'pending', progress: 100, indeterminate: false, cancelable: false, details: '', badge: '' };
        case 'failed':
            return { message: readFailureMessage(row.failure ?? 'download_failed'), state: 'error', progress: 0, indeterminate: false, cancelable: false, details: row.label, badge: '' };
    }
};

const renderAiRowActions = (context: WizardViewContext, row: AiSetupRow): string => {
    const buttons = row.actions.map((action) => {
        const label = context.sanitizer.html(readActionLabel(action));
        return `<button type="button" class="ui-button ui-button--sm ui-variant-neutral" data-action="wizard-ai-row-action" data-ai-row-action="${action}" data-ai-row="${context.sanitizer.attribute(row.key)}" aria-label="${label}" data-tooltip="${label}">${label}</button>`;
    });
    return buttons.join('');
};

const renderAiProgressRow = (context: WizardViewContext, row: AiSetupRow): string => `<div class="wizard-ai-progress-item" data-ai-row="${context.sanitizer.attribute(row.key)}" tabindex="-1"><div class="wizard-ai-progress-slot" data-ai-row-progress></div><div class="wizard-ai-row-actions${row.actions.length === 0 ? ' u-hidden' : ''}" data-ai-row-actions data-ai-actions="${context.sanitizer.attribute(row.actions.join(','))}">${renderAiRowActions(context, row)}</div></div>`;

const readReadyCountText = (summary: AiSetupProgressSummary): string => i18n.t('wizard.aiSetup.progress.readyCount', { ready: summary.readyCount, total: summary.modelCount });

const renderAiProgressStep = (context: WizardViewContext, summary: AiSetupProgressSummary): string => {
    const rows = summary.rows.map((row) => renderAiProgressRow(context, row)).join('');
    return `<div class="wizard-step wizard-step--ai">${renderAiSetupHeading(context, i18n.t('wizard.aiSetup.progress.heading'), i18n.t('wizard.aiSetup.progress.description'))}<p class="wizard-ai-ready-count" role="status" aria-live="polite" data-ai-ready-count>${context.sanitizer.html(readReadyCountText(summary))}</p><div class="ui-operation-progress-list wizard-ai-progress" data-ai-progress-list>${rows}</div></div>`;
};

const renderAiCompletionSummary = (context: WizardViewContext, view: AiSetupCompletionView): string => {
    const ready = i18n.plural('wizard.aiSetup.completion.modelsReady', view.readyNames.length, { count: view.readyNames.length });
    const preparing = view.preparingCount > 0 ? i18n.plural('wizard.aiSetup.completion.stillPreparing', view.preparingCount, { count: view.preparingCount }) : '';
    const detail = [view.readyNames.join(', '), preparing].filter(Boolean).join(' · ');
    return `<div class="wizard-summary-item"><div class="wizard-summary-icon">${renderIcon(context, 'model-default', 24)}</div><div><h3>${context.sanitizer.html(i18n.t('wizard.aiSetup.completion.modelsTitle'))}</h3><p>${context.sanitizer.html(ready)}</p>${detail ? `<p class="wizard-summary-detail">${context.sanitizer.html(detail)}</p>` : ''}</div></div>`;
};

export { describeAiSetupRow, readReadyCountText, renderAiCompletionSummary, renderAiProgressRow, renderAiProgressStep, renderAiRowActions };
