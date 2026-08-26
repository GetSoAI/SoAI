/* SoAI - Shared routing stream item deletion [frontend/assets/ts/core/routing/pages/collections/streamItemDeletion.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { StreamActionHandle, StreamCompletionStatus, StreamFinishedValue, StreamHandleTrackerContract } from '@core/routing/pages/pagetypes/public.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { isArray, isObject, isString } from '@core/typeGuards.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import { ensureError } from '@core/errors/coerce.ts';

interface StreamItemDeletionHost {
    deletingItems: Set<string>;
    streams: StreamHandleTrackerContract;

    optionalUI: (selector: string, context?: Element) => Element | null;
    addClassName: (element: Element, className: string) => void;
    removeClassName: (element: Element, className: string) => void;
    showNotification: (message: string, type: NotificationType) => void;
    handleError: (error: Error, title: string, options?: { notify?: boolean }) => void;
    renderItems: () => void;
    removeItemById: (identifier: string) => void;
}

interface StreamItemDeletionConfig {
    identifier: string;
    confirmTitle: string;
    confirmMessage: string;
    confirmButton: string;
    cancelButton: string;
    getStream: () => Promise<StreamActionHandle>;
    gridSelector: string;
    findCard: (grid: HTMLElement | null, identifier: string) => HTMLElement | null;
    pendingClass: string;
    successMessage: string;
    onAccepted?: (taskId: string) => void;
    projectLocally?: boolean;
}

const requireDeletionResult = (value: StreamFinishedValue): JsonObject | StreamCompletionStatus => {
    if (!isObject(value) || isArray(value)) {
        throw new Error('Deletion stream returned an invalid result payload');
    }
    return value;
};

export const executeStreamItemDeletion = async (host: StreamItemDeletionHost, config: StreamItemDeletionConfig): Promise<void> => {
    const { identifier, confirmTitle, confirmMessage, confirmButton, cancelButton, getStream, gridSelector, findCard, pendingClass, successMessage, onAccepted, projectLocally = true } = config;

    const normalizedIdentifier = isString(identifier) ? identifier.trim() : '';
    if (!normalizedIdentifier) {
        throw new Error('Item deletion requires a non-empty identifier');
    }
    if (host.deletingItems.has(normalizedIdentifier)) {
        return;
    }

    const confirmed = await requireDialogsService().showConfirmation({
        title: confirmTitle,
        message: confirmMessage,
        confirmText: confirmButton,
        cancelText: cancelButton
    });
    if (!confirmed) {
        return;
    }

    const grid = host.optionalUI(gridSelector);
    const gridElement = grid instanceof HTMLElement ? grid : null;
    const card = findCard(gridElement, normalizedIdentifier);
    if (card) {
        host.addClassName(card, pendingClass);
    }

    host.deletingItems.add(normalizedIdentifier);
    try {
        const stream = await getStream();
        if (onAccepted) {
            if (!stream.accepted) throw new Error('Deletion task did not expose accepted task ownership');
            onAccepted(await stream.accepted);
        }
        host.streams.track(normalizedIdentifier, stream);
        const rawResult = await stream.finished;
        const result = requireDeletionResult(rawResult);
        const cancelledValue = 'cancelled' in result ? result.cancelled : null;
        if (cancelledValue === true) {
            return;
        }
        const successValue = 'success' in result ? result.success : null;
        if (successValue !== true && successValue !== false) {
            throw new Error('Deletion stream result must include success=true|false');
        }
        if (successValue === false) {
            const messageValue = 'message' in result ? result.message : null;
            const errorMessage = isString(messageValue) && messageValue.trim() ? messageValue.trim() : successMessage;
            throw new Error(errorMessage);
        }

        if (projectLocally) host.removeItemById(normalizedIdentifier);
        if (card) {
            card.remove();
        }

        const messageValue = 'message' in result ? result.message : null;
        const notifyMessage = isString(messageValue) && messageValue.trim() ? messageValue.trim() : successMessage;
        host.showNotification(notifyMessage, 'success');
    } catch (error) {
        const runtimeError = ensureError(error);
        host.handleError(runtimeError, 'Failed to delete item', { notify: true });
        if (card) {
            host.removeClassName(card, pendingClass);
        }
        host.renderItems();
    } finally {
        host.streams.release(normalizedIdentifier);
        host.deletingItems.delete(normalizedIdentifier);
        if (card) {
            host.removeClassName(card, pendingClass);
        }
    }
};

export type { StreamItemDeletionHost, StreamItemDeletionConfig };
