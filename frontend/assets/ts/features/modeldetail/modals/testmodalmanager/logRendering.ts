/* SoAI - Model test modal log rendering [frontend/assets/ts/features/modeldetail/modals/testmodalmanager/logRendering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import type { TestModalRuntimeContext } from '@features/modeldetail/modals/testmodalmanager/internalContracts.ts';
import type { TestModalLogEntry } from '@features/modeldetail/modals/TestModalManagerTypes.ts';

const LOG_DOM_FLUSH_DELAY_MS = 50;

const formatLogEntry = (entry: TestModalLogEntry): string => {
    const timestamp = entry['timestamp'];
    const component = entry['component'];
    const level = entry['level'];
    const text = entry['text'];
    const message = entry['message'];
    return [timestamp, component, level, text || message].filter(Boolean).join(' | ');
};

const requireLogsContainer = (context: TestModalRuntimeContext): HTMLElement | null => {
    const container = context.host.view.optionalUI(modalUiSelector(context.modalId, 'logs'), context.modalRoot);
    if (!container) {
        return null;
    }
    if (!(container instanceof HTMLElement)) {
        throw new TypeError(`${modalUiSelector(context.modalId, 'logs')} must be an HTMLElement`);
    }
    return container;
};

const clearPendingLogFlush = (context: TestModalRuntimeContext): void => {
    if (context.state.logFlushTimerId !== null) {
        context.host.view.clearTimer(context.state.logFlushTimerId);
        context.state.logFlushTimerId = null;
    }
};

const trimRenderedLogEntries = (container: HTMLElement, lineLimit: number): void => {
    const entries = dom.resolveAll('.model-test-log-entry:not(.model-test-log-summary)', container);
    const overflow = entries.length - lineLimit;
    if (overflow <= 0) {
        return;
    }
    entries.slice(0, overflow).forEach((entry) => entry.remove());
};

const flushPendingLogEntries = (context: TestModalRuntimeContext): boolean => {
    clearPendingLogFlush(context);
    if (!context.state.pendingLogEntries.length) {
        return false;
    }

    const pendingEntries = context.state.pendingLogEntries.splice(0);
    const logContainer = requireLogsContainer(context);
    if (logContainer) {
        const documentRef = context.host.model.getDocument();
        const fragment = documentRef.createDocumentFragment();
        pendingEntries.forEach((entryObject): void => {
            const logElement = documentRef.createElement('div');
            logElement.className = 'model-test-log-entry';
            const level = entryObject['level'];
            if (level) {
                logElement.setAttribute('data-level', String(level).toUpperCase());
            }
            logElement.textContent = formatLogEntry(entryObject);
            fragment.appendChild(logElement);
        });
        logContainer.appendChild(fragment);
        trimRenderedLogEntries(logContainer, context.state.logLineLimit);
        context.host.view.updateProperty(logContainer, 'scrollTop', logContainer.scrollHeight);
    }
    return true;
};

const schedulePendingLogFlush = (context: TestModalRuntimeContext, onFlushed: () => void): void => {
    if (context.state.logFlushTimerId !== null) {
        return;
    }
    context.state.logFlushTimerId = context.host.view.setTimer((): void => {
        if (flushPendingLogEntries(context)) {
            onFlushed();
        }
    }, LOG_DOM_FLUSH_DELAY_MS);
};

export { clearPendingLogFlush, flushPendingLogEntries, formatLogEntry, requireLogsContainer, schedulePendingLogFlush };
