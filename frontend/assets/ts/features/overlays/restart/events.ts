/* SoAI - Overlays feature restart events [frontend/assets/ts/features/overlays/restart/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { handleApiResult } from '@core/api/apiResultHandler.ts';
import { dom } from '@core/dom/dom.ts';
import { getLocation, requireDocument } from '@core/environment/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { reloadCurrentLocation } from '@features/overlays/restart/actions.ts';
import { DEFAULT_MAX_RETRIES, RESTART_STATUS_ICON_HIDDEN_CLASS } from '@features/overlays/restart/constants.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import type { ApiInterface, OperationType, OverlayElements, RestartSessionRepository } from '@features/overlays/restart/types.ts';

interface RestartBackendStatusInput {
    currentRetry: number;
    currentType: OperationType | null;
    description: HTMLElement | null;
    api: ApiInterface;
    interruptionObserved: boolean;
    observeTransition: boolean;
    updateText: (element: HTMLElement, value: string) => void;
}

interface RestartBackendStatusResult {
    isOnline: boolean;
    currentRetry: number;
    interruptionObserved: boolean;
}

interface RestartBackendOnlineInput {
    currentType: OperationType | null;
    elements: OverlayElements;
    api: ApiInterface;
    updateText: (element: HTMLElement, value: string) => void;
    setTimer: (callback: () => void | Promise<void>, delayMs: number) => number | null;
    showNotification: (message: string, type: NotificationType) => void;
    hide: () => void;
}

interface RestartMaxRetriesInput {
    currentRetry: number;
    maxRetries: number;
    currentType: OperationType | null;
    successTimer: number | null;
    elements: OverlayElements;
    repository: RestartSessionRepository;
    updateText: (element: HTMLElement, value: string) => void;
    setTimer: (callback: () => void | Promise<void>, delayMs: number) => number | null;
    clearTimer: (id: number) => void;
    addEventListener: (target: HTMLElement, event: string, handler: (event: Event) => void) => void;
    addClassName: (target: HTMLElement, className: string) => void;
    removeClassName: (target: HTMLElement, className: string) => void;
    stopPolling: () => void;
}

interface RestartDomReadyHost {
    addDomReadyListener: (listener: () => void) => (() => void) | null;
}

const awaitRestartDomReady = async (host: RestartDomReadyHost): Promise<void> => {
    const doc = requireDocument();
    if (doc.readyState === 'interactive' || doc.readyState === 'complete') {
        return;
    }
    const deferred = createDeferred<void>();
    let dispose: (() => void) | null = null;
    const handler = (): void => {
        if (dispose) {
            dispose();
        }
        deferred.resolve();
    };
    dispose = host.addDomReadyListener(handler);
    await deferred.promise;
};

const checkRestartBackendStatus = async (input: RestartBackendStatusInput): Promise<RestartBackendStatusResult> => {
    const awaitingInterruption = input.observeTransition && !input.interruptionObserved;
    const currentRetry = awaitingInterruption ? input.currentRetry : input.currentRetry + 1;

    if (input.currentType === 'connection-lost' && input.description) {
        input.updateText(input.description, i18n.t('restartOverlay.reconnecting'));
    }

    const result = await handleApiResult(input.api.system.health({ timeoutMs: 5000 }), {
        boundaryName: 'RestartOverlay',
        silent: true,
        notifyOnError: false,
        rethrow: false,
        logErrors: false
    });

    const interruptionObserved = input.interruptionObserved || (input.observeTransition && !result);
    const online = Boolean(result) && (!input.observeTransition || interruptionObserved);
    const status =
        online && input.observeTransition
            ? await handleApiResult(input.api.system.status(), {
                  boundaryName: 'RestartOverlay',
                  silent: true,
                  notifyOnError: false,
                  rethrow: false,
                  logErrors: false
              })
            : null;
    return {
        isOnline: online && (!input.observeTransition || (Boolean(status) && status?.mainState !== 'stopping')),
        currentRetry,
        interruptionObserved
    };
};

const handleRestartBackendOnline = (input: RestartBackendOnlineInput): number | null => {
    const { message, description } = input.elements;
    const completedType = input.currentType;
    if (message) input.updateText(message, i18n.t('common.connection.backOnline'));
    if (description) input.updateText(description, i18n.t('common.connection.restored'));

    return input.setTimer(async () => {
        input.hide();

        if (completedType === 'update-soai') {
            reloadCurrentLocation(getLocation);
        } else {
            await input.api.initialize();
            input.showNotification(i18n.t('common.notifications.backOnline'), 'success');
        }
    }, 1500);
};

const handleRestartMaxRetriesReached = (input: RestartMaxRetriesInput): number | null => {
    const { message, description } = input.elements;
    input.stopPolling();
    if (input.elements.overlay) {
        if (input.maxRetries === DEFAULT_MAX_RETRIES && input.currentRetry >= DEFAULT_MAX_RETRIES) {
            input.addClassName(input.elements.overlay, RESTART_STATUS_ICON_HIDDEN_CLASS);
        } else {
            input.removeClassName(input.elements.overlay, RESTART_STATUS_ICON_HIDDEN_CLASS);
        }
    }

    if (input.currentType === 'system-reboot') {
        if (message) input.updateText(message, i18n.t('restartOverlay.messages.rebootTimeout'));
        if (description) input.updateText(description, i18n.t('restartOverlay.descriptions.rebootTimeout'));

        input.repository.clear();

        if (input.successTimer) {
            input.clearTimer(input.successTimer);
        }
        return null;
    }

    if (message) input.updateText(message, i18n.t('common.connection.timeout'));
    if (description) {
        const infoText = i18n.t('common.connection.timeoutDescription', { 'max_retries': input.maxRetries });
        const fragment = dom.createFragment();
        const textNode = dom.create('span', { className: 'restart-timeout-message' });
        input.updateText(textNode, infoText);
        const lineBreak = dom.create('br');
        const reloadButton = dom.create('button', {
            className: 'ui-button ui-variant-accent restart-reload-button',
            type: 'button'
        });
        input.updateText(reloadButton, i18n.t('common.connection.reloadPage'));
        input.addEventListener(reloadButton, 'click', () => {
            reloadCurrentLocation(getLocation);
        });
        dom.appendChild(fragment, [textNode, lineBreak, reloadButton]);
        dom.replaceContent(description, fragment, { escape: false });
    }

    return null;
};

export { awaitRestartDomReady, checkRestartBackendStatus, handleRestartBackendOnline, handleRestartMaxRetriesReached };
