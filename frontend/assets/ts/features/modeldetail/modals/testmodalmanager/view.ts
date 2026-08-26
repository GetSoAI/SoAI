/* SoAI - Model test modal rendering [frontend/assets/ts/features/modeldetail/modals/testmodalmanager/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { i18n } from '@core/i18n/index.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { EMPTY_UI_HTML } from '@core/security/uiHtml.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isObject, isString } from '@core/typeGuards.ts';
import type { TestModalRuntimeContext } from '@features/modeldetail/modals/testmodalmanager/internalContracts.ts';
import { clearPendingLogFlush, flushPendingLogEntries, formatLogEntry, requireLogsContainer, schedulePendingLogFlush } from '@features/modeldetail/modals/testmodalmanager/logRendering.ts';

const LOGS_PLACEHOLDER_CLASS = 'model-test-logs-placeholder';

export const resolveModelPluginName = (context: TestModalRuntimeContext): string => {
    const model = context.host.model.getModel();
    const modelObject = isObject(model) ? model : null;
    const candidates = modelObject ? [modelObject['plugin'], modelObject['pluginName'], modelObject['providerName'], modelObject['provider']] : [];
    const resolvedCandidate = candidates.find((candidate): candidate is string => isString(candidate) && candidate.trim().length > 0);
    const resolved = resolvedCandidate ?? '';
    return resolved.toLowerCase().trim();
};

const updateLogsPlaceholder = (context: TestModalRuntimeContext): void => {
    const container = requireLogsContainer(context);
    if (!container) {
        return;
    }

    const placeholder = context.host.view.optionalUI(`.${LOGS_PLACEHOLDER_CLASS}`, container);
    if (context.state.logEntries.length > 0) {
        placeholder?.remove();
        return;
    }

    if (placeholder) {
        return;
    }

    const placeholderElement = context.host.model.getDocument().createElement('div');
    placeholderElement.className = LOGS_PLACEHOLDER_CLASS;
    placeholderElement.textContent = i18n.t('modelDetail.modal.test.logsEmpty');
    container.appendChild(placeholderElement);
};

export const updateToggleLogsButton = (context: TestModalRuntimeContext): void => {
    const button = context.host.view.optionalUI(modalUiSelector(context.modalId, 'toggle-logs'), context.modalRoot);
    if (!button) {
        return;
    }

    const hasLogs = context.state.logEntries.length > 0;
    const testStarted = context.state.active || context.state.completed;
    context.host.view.toggleClassName(button, 'u-hidden', !hasLogs || !testStarted);

    if (hasLogs && testStarted) {
        const isCollapsed = context.state.logsCollapseController?.isCollapsed() ?? true;
        context.host.view.updateText(button, isCollapsed ? i18n.t('modelDetail.modal.test.showLogs') : i18n.t('modelDetail.modal.test.hideLogs'));
    }
};

export const updateCopyLogsButtonState = (context: TestModalRuntimeContext): void => {
    context.host.view.toggleClassName(context.host.view.optionalUI(modalUiSelector(context.modalId, 'copy-logs'), context.modalRoot), 'u-hidden', !context.state.logEntries.length || !context.host.view.hasClipboardSupport());
};

export const clearLogs = (context: TestModalRuntimeContext): void => {
    clearPendingLogFlush(context);
    context.state.logEntries = [];
    context.state.pendingLogEntries = [];
    const container = context.host.view.optionalUI(modalUiSelector(context.modalId, 'logs'), context.modalRoot);
    if (container) {
        context.host.view.updateHTML(container, EMPTY_UI_HTML);
    }
    updateLogsPlaceholder(context);
    updateCopyLogsButtonState(context);
};

export const setLogsVisible = (context: TestModalRuntimeContext, setupLogsCollapse: () => void): void => {
    updateLogsPlaceholder(context);
    context.host.view.toggleClassName(context.host.view.optionalUI(modalUiSelector(context.modalId, 'logs-card'), context.modalRoot), 'u-hidden', false);
    if (!context.state.logsCollapseController) {
        setupLogsCollapse();
    }
    updateToggleLogsButton(context);
};

export const hideLogs = (context: TestModalRuntimeContext): void => {
    context.host.view.toggleClassName(context.host.view.optionalUI(modalUiSelector(context.modalId, 'logs-card'), context.modalRoot), 'u-hidden', true);
    updateToggleLogsButton(context);
};

export const setupLogsCollapse = (context: TestModalRuntimeContext, onStateChange: () => void): void => {
    if (context.state.logsCollapseController) {
        return;
    }

    const card = context.host.view.optionalUI(modalUiSelector(context.modalId, 'logs-card'), context.modalRoot);
    if (!card) {
        return;
    }

    const toggleButton = context.host.view.optionalUI(modalUiSelector(context.modalId, 'logs-toggle'), context.modalRoot);
    if (toggleButton) {
        const iconMarkup = context.host.workflow.getIconSync('chevron-left', { size: 14, strokeWidth: 2 });
        if (iconMarkup) {
            context.host.view.updateHTML(toggleButton, iconMarkup, { escape: false });
        }
    }

    context.state.logsCollapseController = context.host.workflow.createLogsCollapseController({
        card,
        contentSelector: '[data-card-content]',
        titleBarSelector: '.model-test-logs-header',
        toggleButtonSelector: modalUiSelector(context.modalId, 'logs-toggle'),
        toggleButtonCollapsedClass: 'model-test-logs-toggle--collapsed',
        collapsedClass: 'is-collapsed',
        contentCollapsedClass: 'is-collapsed',
        animate: true,
        animationDuration: 320,
        animationEasing: 'ease',
        initialCollapsed: true,
        persistKey: 'test-modal-logs-collapsed',
        guardSelector: 'button, a, input, select, textarea, [data-ignore-collapse]',
        onStateChange: (): void => {
            updateLogsPlaceholder(context);
            onStateChange();
        }
    });
};

export const toggleLogsCollapse = (context: TestModalRuntimeContext): void => {
    const controller = context.state.logsCollapseController;
    if (!controller) {
        return;
    }

    const wasCollapsed = controller.isCollapsed();
    controller.toggle();
    updateToggleLogsButton(context);

    if (wasCollapsed) {
        context.host.view.setTimer((): void => {
            const modalBody = context.host.view.optionalUI('.modal-body', context.modalRoot);
            if (modalBody) {
                modalBody.scrollTop = modalBody.scrollHeight;
            }
        }, 350);
    }
};

const updateLogFlushState = (context: TestModalRuntimeContext): void => {
    updateLogsPlaceholder(context);
    updateCopyLogsButtonState(context);
    updateToggleLogsButton(context);
};

export const appendLogEntry = (context: TestModalRuntimeContext, entry: JsonValue | null | undefined): void => {
    if (!entry || !(context.state.active || context.state.completed)) {
        return;
    }

    const entryObject = isObject(entry) ? entry : null;
    if (!entryObject) {
        return;
    }

    const hadLogs = context.state.logEntries.length > 0;
    context.state.logEntries.push(entryObject);
    context.state.pendingLogEntries.push(entryObject);
    if (context.state.logEntries.length > context.state.logLineLimit) {
        context.state.logEntries.splice(0, context.state.logEntries.length - context.state.logLineLimit);
    }

    if (!hadLogs) {
        setLogsVisible(context, (): void => {
            setupLogsCollapse(context, (): void => {
                updateToggleLogsButton(context);
            });
        });
        updateCopyLogsButtonState(context);
        updateToggleLogsButton(context);
    }

    schedulePendingLogFlush(context, (): void => updateLogFlushState(context));
};

export const copyLogs = (context: TestModalRuntimeContext): void => {
    if (!context.state.logEntries.length) {
        return;
    }

    terminateHandledPromise(context.host.view.copyToClipboard(context.state.logEntries.map(formatLogEntry).join('\n')));
};

export const appendFinalLogEntry = (context: TestModalRuntimeContext, status: string, message: string): void => {
    if (flushPendingLogEntries(context)) {
        updateLogFlushState(context);
    }
    const container = requireLogsContainer(context);
    if (!container) {
        return;
    }

    const row = context.host.model.getDocument().createElement('div');
    const badge = context.host.model.getDocument().createElement('div');
    row.className = 'model-test-log-entry model-test-log-summary';
    const variant = status === 'success' ? 'success' : status === 'cancelled' ? 'neutral' : 'error';
    badge.className = `ui-status-badge ${variant}`;
    badge.textContent = context.host.view.sanitizeText(message, { allowEmpty: true });
    row.appendChild(badge);
    container.appendChild(row);
    context.host.view.updateProperty(container, 'scrollTop', container.scrollHeight);
};
