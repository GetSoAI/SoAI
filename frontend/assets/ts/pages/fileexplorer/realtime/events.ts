/* SoAI - Mounted filesystem listing event and reconnect ownership [frontend/assets/ts/pages/fileexplorer/realtime/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { showPersistentNotification, dismissPersistentNotificationsByDedupeKey } from '@core/ui/notifications/notifications.ts';
import { resolveFileExplorerBrowserErrorMessage } from '@pages/fileexplorer/controllers/fileExplorerHttpErrorController.ts';
import { getAuthManager } from '@core/auth/public.ts';
import { getWebSocketClient, isCurrentWebSocketClient } from '@core/websocketclient/service.ts';
import { createWebSocketContractBinding, subscribeManagedWebSocketContracts, subscribeManagedWebSocketContract } from '@core/realtime/websocketBatchSubscription.ts';
import type { DirectoryListingReleaseRecovery } from '@core/fileexplorerbrowser/directoryListingContracts.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { runCleanupStepCollectingFailure, throwCollectedCleanupFailures } from '@core/lifecycle/cleanup.ts';
import { WEBSOCKET_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/registry.ts';
import type { StreamTransport } from '@core/realtime/streammanager/streamTransport.ts';
import { WEBSOCKET_LIFECYCLE_EVENT_TYPES } from '@core/websocketEvents.ts';

interface FileExplorerListingEventsOptions {
    readonly connection: Pick<StreamTransport, 'subscribeEvents' | 'subscribeConnected'>;
    readonly signal: AbortSignal | null;
    readonly isCurrent: () => boolean;
    readonly invalidate: () => Promise<boolean>;
    readonly recover: () => Promise<boolean>;
}

const subscribeFileExplorerListingEvents = (options: FileExplorerListingEventsOptions): (() => void) => {
    const cleanups: Array<() => void> = [];
    let active = true;
    let invalidPayloadReported = false;
    const cleanup = (): void => {
        active = false;
        const failures: Error[] = [];
        while (cleanups.length) runCleanupStepCollectingFailure(() => cleanups.pop()?.(), failures);
        throwCollectedCleanupFailures(failures);
    };
    const isCurrent = (): boolean => active && !options.signal?.aborted && options.isCurrent();
    const observe = (operation: Promise<boolean>): void => {
        void operation.catch((error) => errorHandler.warn('FileExplorer', 'Listing event reconciliation failed', ensureError(error)));
    };
    const invalidate = (): void => {
        if (isCurrent()) observe(options.invalidate());
    };
    try {
        cleanups.push(
            subscribeManagedWebSocketContract({
                label: 'FileExplorer',
                contract: WEBSOCKET_EVENT_CONTRACTS.fileSystem.changed,
                signal: options.signal,
                handler: () => {
                    invalidPayloadReported = false;
                    invalidate();
                },
                onInvalidPayload: (error) => {
                    if (!isCurrent()) return;
                    if (!invalidPayloadReported) errorHandler.warn('FileExplorer', 'Rejected filesystem invalidation; reconciling the authoritative listing', error);
                    invalidPayloadReported = true;
                    invalidate();
                }
            })
        );
        cleanups.push(
            options.connection.subscribeEvents((eventType) => {
                if (eventType === WEBSOCKET_LIFECYCLE_EVENT_TYPES.DISCONNECTED) invalidate();
            })
        );
        cleanups.push(
            options.connection.subscribeConnected(() => {
                if (!isCurrent()) return;
                invalidPayloadReported = false;
                observe(options.recover());
            })
        );
    } catch (error) {
        const failures = [ensureError(error)];
        runCleanupStepCollectingFailure(cleanup, failures);
        throwCollectedCleanupFailures(failures);
    }
    return cleanup;
};

const subscribeFileExplorerReleaseRecovery: DirectoryListingReleaseRecovery = (recover, authEnded, failure, listingId) => {
    const notificationKey = `listing-release:${listingId}`;
    showPersistentNotification({ message: `${i18n.t('pageOutlet.errors.resourceReleaseUnconfirmed')} ${resolveFileExplorerBrowserErrorMessage(failure)}`, type: 'warning', dedupeKey: notificationKey, buttons: [] });
    const client = getWebSocketClient();
    const unsubscribe = subscribeManagedWebSocketContracts({
        label: 'FileExplorerRelease',
        subscribe: (type, handler) => client.subscribe(type, handler),
        events: [
            createWebSocketContractBinding({
                contract: WEBSOCKET_EVENT_CONTRACTS.lifecycle.connected,
                handler: (_payload, context) => {
                    if (isCurrentWebSocketClient(client) && context.connectionEpoch === client.connectionEpoch) recover();
                }
            })
        ]
    });
    const unsubscribeAuth = getAuthManager().onEpochIntent(() => authEnded());
    return () => {
        unsubscribe();
        unsubscribeAuth();
        dismissPersistentNotificationsByDedupeKey(notificationKey);
    };
};

export { subscribeFileExplorerListingEvents, subscribeFileExplorerReleaseRecovery };
