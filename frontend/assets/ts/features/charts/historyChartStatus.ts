/* SoAI - Charts feature history chart status [frontend/assets/ts/features/charts/historyChartStatus.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { insertWithPresence, isPresenceExiting, removeWithPresence } from '@core/animations/presence/public.ts';
import { CSS_CLASSES } from '@core/cssConstants.ts';
import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';

const STATUS_CLASS = 'history-chart-status';
const MESSAGE_CLASS = 'history-chart-status__message';
const SPINNER_CLASS = 'history-chart-status__spinner';
const RETRY_CLASS = 'history-chart-status__retry';

interface HistoryChartStatusView {
    message: string;
    tone: string | null;
    overlay: boolean;
    retryAction: string | null;
}

const createStatusPart = (tagName: string, className: string): HTMLElement => dom.create(tagName, { className, includeIdClass: false });

const resolveStatusPart = (element: HTMLElement, className: string, tagName: string): HTMLElement => {
    const existing = dom.resolve(`:scope > .${className}`, element);
    if (existing instanceof HTMLElement) {
        return existing;
    }
    const created = createStatusPart(tagName, className);
    element.prepend(created);
    return created;
};

const resolveHistoryChartStatusElement = (container: HTMLElement): HTMLElement => {
    const existing = dom.resolve(`:scope > .${STATUS_CLASS}`, container);
    if (existing instanceof HTMLElement) {
        return existing;
    }
    const created = createStatusPart('div', `${STATUS_CLASS} ${CSS_CLASSES.HIDDEN}`);
    created.setAttribute('role', 'status');
    created.setAttribute('aria-live', 'polite');
    container.appendChild(created);
    return created;
};

const syncRetryButton = (element: HTMLElement, retryAction: string | null): void => {
    const existing = dom.resolve(`:scope > .${RETRY_CLASS}`, element);
    const button = existing instanceof HTMLButtonElement && !isPresenceExiting(existing) ? existing : null;
    if (!retryAction) {
        if (button) {
            removeWithPresence(button);
        }
        return;
    }
    if (button) {
        button.dataset['action'] = retryAction;
        return;
    }
    const created = dom.create('button', {
        type: 'button',
        className: `ui-button ui-button--sm ui-variant-neutral ${RETRY_CLASS}`,
        dataset: { action: retryAction },
        textContent: i18n.t('pageOutlet.retry'),
        includeIdClass: false
    });
    insertWithPresence(element, created);
};

const renderHistoryChartStatus = (element: HTMLElement, view: HistoryChartStatusView | null): void => {
    const message = resolveStatusPart(element, MESSAGE_CLASS, 'span');
    const existingSpinner = dom.resolve(`:scope > .${SPINNER_CLASS}`, element);
    if (view?.tone === 'loading') {
        if (!existingSpinner) {
            const spinner = createStatusPart('span', `loading-spinner ${SPINNER_CLASS}`);
            spinner.setAttribute('aria-hidden', 'true');
            element.prepend(spinner);
        }
    } else existingSpinner?.remove();
    if (!view) {
        message.textContent = '';
        element.classList.add(CSS_CLASSES.HIDDEN);
        element.removeAttribute('data-tone');
        element.removeAttribute('data-overlay');
        syncRetryButton(element, null);
        return;
    }
    message.textContent = view.tone === 'loading' ? `${view.message}...` : view.message;
    element.classList.remove(CSS_CLASSES.HIDDEN);
    if (view.tone) {
        element.dataset['tone'] = view.tone;
    } else {
        element.removeAttribute('data-tone');
    }
    if (view.overlay) {
        element.dataset['overlay'] = 'true';
    } else {
        element.removeAttribute('data-overlay');
    }
    syncRetryButton(element, view.retryAction);
};

export { renderHistoryChartStatus, resolveHistoryChartStatusElement };
export type { HistoryChartStatusView };
