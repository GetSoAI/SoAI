/* SoAI - Shared operation progress events [frontend/assets/ts/core/operationprogress/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { dom } from '@core/dom/dom.ts';
import { isFunction } from '@core/typeGuards.ts';
import type { OperationProgressOptions, OperationProgressReporter } from '@core/operationprogress/types.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';

interface OperationProgressEventHost extends OperationProgressReporter {
    options: OperationProgressOptions;
}

const resolveCancelButton = (event: MouseEvent, selector: string): HTMLButtonElement | null => {
    const target = event.target;
    if (!(target instanceof Element)) {
        return null;
    }
    const closestButton = target.closest(selector);
    return closestButton instanceof HTMLButtonElement ? closestButton : null;
};

const resolveProgressElement = (button: HTMLButtonElement): HTMLElement | null => {
    const progressElement = button.closest('[data-operation-progress-key]');
    return progressElement instanceof HTMLElement ? progressElement : null;
};

const restoreCancelButtonAfterFailure = (button: HTMLButtonElement): void => {
    button.disabled = false;
    button.setAttribute('aria-disabled', 'false');
    delete button.dataset['cancelRequested'];
};

const reportCancellationFailure = (host: OperationProgressEventHost, key: string, button: HTMLButtonElement, error: Error): void => {
    restoreCancelButtonAfterFailure(button);
    errorHandler.warn('OperationProgress', 'Cancellation request failed', error);
    if (!button.isConnected || !host.hasActiveOperations()) return;
    try {
        host.update(key, {
            details: i18n.t('common.cancellation.failed'),
            cancelable: true
        });
    } catch (updateError) {
        errorHandler.error('OperationProgress', 'Cancellation failure state update failed', ensureError(updateError));
    }
};

const handleOperationProgressContainerClick = (host: OperationProgressEventHost, event: MouseEvent): void => {
    const selector = host.options.cancelSelector;
    if (!selector) {
        return;
    }

    const button = resolveCancelButton(event, selector);
    if (!button) {
        return;
    }

    const progressElement = resolveProgressElement(button);
    if (!progressElement) {
        return;
    }

    const key = dom.getData(progressElement, 'operationProgressKey');
    if (!key) {
        return;
    }

    event.preventDefault();
    event.stopPropagation();

    button.setAttribute('aria-disabled', 'true');
    button.disabled = true;
    button.dataset['cancelRequested'] = '1';

    if (!isFunction(host.options.onCancel)) {
        reportCancellationFailure(host, key, button, new Error('Operation cancellation handler is unavailable'));
        return;
    }

    try {
        const cancelResult = host.options.onCancel(key, {
            button,
            element: progressElement,
            reporter: host
        });
        if (cancelResult && typeof cancelResult.then === 'function') {
            const handleAsyncCancel = async (): Promise<void> => {
                try {
                    await cancelResult;
                } catch (error) {
                    reportCancellationFailure(host, key, button, ensureError(error));
                }
            };
            terminateHandledPromise(handleAsyncCancel());
        }
    } catch (error) {
        reportCancellationFailure(host, key, button, ensureError(error));
    }
};

export { handleOperationProgressContainerClick };
