/* SoAI - Frontend operation progress ownership [frontend/assets/ts/core/operationprogress/operationProgress.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { isHTMLElement, isString } from '@core/typeGuards.ts';
import { createProgressElement, updateProgressElement } from '@core/operationprogress/dom.ts';
import { handleOperationProgressContainerClick } from '@core/operationprogress/events.ts';
import { normalizeOperationProgressOptions, readOperationProgressUpdatePayload } from '@core/operationprogress/payloads.ts';
import type { OperationProgressData, OperationProgressOptions, OperationProgressReporter } from '@core/operationprogress/types.ts';

interface OperationProgressService {
    createOperationProgressReporter(container: HTMLElement | string, options?: OperationProgressOptions | null): OperationProgressReporter;
}

const resolveContainerElement = (container: HTMLElement | string): HTMLElement => {
    if (isHTMLElement(container)) {
        return container;
    }
    if (!isString(container) || !container.trim()) {
        throw new TypeError('Operation progress container must be an HTMLElement or non-empty selector');
    }
    const selector = container.startsWith('#') ? container : `#${container}`;
    const resolved = dom.resolve(selector);
    if (!(resolved instanceof HTMLElement)) {
        throw new Error(`Operation progress container not found: ${selector}`);
    }
    return resolved;
};

const resolveBackgroundButton = (buttonId: string | null): HTMLElement | null => {
    if (!buttonId) {
        return null;
    }
    const selector = buttonId.startsWith('#') ? buttonId : `#${buttonId}`;
    const resolved = dom.resolve(selector);
    if (!(resolved instanceof HTMLElement)) {
        throw new Error(`Operation progress background button not found: ${selector}`);
    }
    return resolved;
};

const createOperationProgressReporter = (container: HTMLElement | string, options: OperationProgressOptions | null = null): OperationProgressReporter => {
    const containerElement = resolveContainerElement(container);
    const normalizedOptions = normalizeOperationProgressOptions(options);
    const progressElements = new Map<string, HTMLElement>();
    const backgroundButton = resolveBackgroundButton(normalizedOptions.backgroundButtonId ?? null);
    let clickListener: ((event: Event) => void) | null = null;
    let destroyed = false;

    const requireActiveReporter = (operation: string): void => {
        if (destroyed) {
            throw new Error(`Operation progress reporter cannot ${operation} after destroy`);
        }
    };

    const syncBackgroundButton = (): void => {
        if (!backgroundButton) {
            return;
        }
        const hasActiveOperations = progressElements.size > 0;
        dom.toggleClass(backgroundButton, 'u-hidden', !hasActiveOperations);
        backgroundButton.setAttribute('aria-hidden', hasActiveOperations ? 'false' : 'true');
    };

    const resolveProgressElement = (key: string): HTMLElement | null => {
        const cached = progressElements.get(key);
        if (cached && cached.isConnected) {
            return cached;
        }
        const candidates = dom.resolveAll('[data-operation-progress-key]', containerElement);
        for (const candidate of candidates) {
            if (!(candidate instanceof HTMLElement)) {
                continue;
            }
            const candidateKey = dom.getData(candidate, 'operationProgressKey');
            if (candidateKey !== key) {
                continue;
            }
            progressElements.set(key, candidate);
            return candidate;
        }
        return null;
    };

    const clearProgressElements = (): void => {
        progressElements.forEach((element) => element.remove());
        progressElements.clear();
        syncBackgroundButton();
    };

    const reporter: OperationProgressReporter = {
        update: (key: string, data: OperationProgressData): void => {
            requireActiveReporter('update');
            if (!key || !isString(key)) {
                throw new TypeError('Operation progress update requires a non-empty operation key');
            }
            const updatePayload = readOperationProgressUpdatePayload(data);

            let progressElement = resolveProgressElement(key);
            if (!progressElement) {
                const initialMessage = updatePayload.messageValue && updatePayload.messageValue.trim() ? updatePayload.messageValue : key;
                progressElement = createProgressElement(key, initialMessage, {
                    showCancel: normalizedOptions.showCancel !== false,
                    showBadge: normalizedOptions.showBadge !== false,
                    extraClassName: normalizedOptions.extraClassName ?? null
                });
                containerElement.append(progressElement);
                progressElements.set(key, progressElement);
            }
            updateProgressElement(progressElement, updatePayload.progressValue, updatePayload.messageValue, updatePayload.badgeValue, updatePayload.detailsValue, updatePayload.stateValue, updatePayload.cancelableValue);
            syncBackgroundButton();
        },
        remove: (key: string): void => {
            requireActiveReporter('remove');
            const progressElement = resolveProgressElement(key);
            if (!progressElement) {
                return;
            }
            progressElement.remove();
            progressElements.delete(key);
            syncBackgroundButton();
        },
        clear: (): void => {
            requireActiveReporter('clear');
            clearProgressElements();
        },
        destroy: (): void => {
            if (destroyed) {
                return;
            }
            destroyed = true;
            if (clickListener) {
                containerElement.removeEventListener('click', clickListener);
                clickListener = null;
            }
            clearProgressElements();
        },
        hasActiveOperations: (): boolean => !destroyed && progressElements.size > 0
    };

    if (normalizedOptions.cancelSelector && normalizedOptions.showCancel !== false) {
        clickListener = (event: Event): void => {
            if (event instanceof MouseEvent) {
                handleOperationProgressContainerClick(
                    {
                        ...reporter,
                        options: normalizedOptions
                    },
                    event
                );
            }
        };
        containerElement.addEventListener('click', clickListener);
    }

    syncBackgroundButton();
    return reporter;
};

const operationProgress: OperationProgressService = {
    createOperationProgressReporter
};

export { operationProgress, createOperationProgressReporter };
export type { OperationProgressService };
