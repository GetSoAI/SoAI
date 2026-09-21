/* SoAI - Shared clipboard operations [frontend/assets/ts/core/clipboard.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getGlobalScope } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import { isFunction, isString } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { NotificationType } from '@core/ui/notifications/types.ts';
import type { StringConvertibleValue } from '@core/pagecontext/contracts.ts';

type NotificationHandler = (message: string, type: NotificationType) => void;
type ClipboardCopyInput = string | number | boolean | bigint | symbol | StringConvertibleValue | null | undefined | void;

interface CopyOptions {
    successMessage?: string;
    errorMessage?: string;
    unavailableMessage?: string;
    showNotification?: boolean;
    notify?: NotificationHandler;
    onSuccess?: () => void;
    onError?: (error: Error) => void;
}

interface GlobalScopeWithClipboard {
    navigator?: {
        clipboard?: {
            writeText: (text: string) => Promise<void>;
        };
    };
    document?: {
        body?: HTMLElement;
        execCommand: (command: string) => boolean;
        createElement: {
            (tagName: 'textarea'): HTMLTextAreaElement;
            (tagName: string): HTMLElement;
        };
    };
}

class ClipboardService {
    private notificationHandlers: Set<NotificationHandler>;
    private scope: GlobalScopeWithClipboard;

    constructor(scope: GlobalScopeWithClipboard | null = null) {
        this.notificationHandlers = new Set();
        this.scope = scope ?? getGlobalScope();
    }

    setNotificationHandler(handler: NotificationHandler | null): () => void {
        this.notificationHandlers.clear();
        return handler ? this.registerNotificationHandler(handler) : () => {};
    }

    registerNotificationHandler(handler: NotificationHandler): () => void {
        if (!isFunction(handler)) {
            return () => {};
        }
        this.notificationHandlers.add(handler);
        return () => this.notificationHandlers.delete(handler);
    }

    #notify(message: string, type: NotificationType, overrideHandler: NotificationHandler | null = null): void {
        if (overrideHandler) {
            this.#invokeHandler(overrideHandler, message, type);
            return;
        }
        if (!this.notificationHandlers.size) {
            return;
        }
        for (const handler of this.notificationHandlers) {
            this.#invokeHandler(handler, message, type);
        }
    }

    #invokeHandler(handler: NotificationHandler, message: string, type: NotificationType): void {
        if (!isFunction(handler)) {
            return;
        }
        try {
            handler(message, type);
        } catch (error) {
            const err = ensureError(error);
            errorHandler.warn('ClipboardService', 'Notification handler failed', err);
        }
    }

    #isSecureClipboardSupported(): boolean {
        const clipboard = this.scope?.navigator?.clipboard;
        return Boolean(clipboard && isFunction(clipboard.writeText));
    }

    #isHttpClipboardSupported(): boolean {
        const doc = this.scope?.document;
        return Boolean(doc?.body && isFunction(doc.execCommand) && isFunction(doc.createElement));
    }

    isSupported(): boolean {
        return this.#isSecureClipboardSupported() || this.#isHttpClipboardSupported();
    }

    async copyText(text: ClipboardCopyInput, options: CopyOptions = {}): Promise<boolean> {
        try {
            const normalized = isString(text) ? text : String(text ?? '');
            const successMessage = options.successMessage ?? i18n.t('common.clipboard.copied');
            const errorMessage = options.errorMessage ?? i18n.t('common.clipboard.copyFailed');
            const unavailableMessage = options.unavailableMessage ?? i18n.t('common.clipboard.copyUnavailable');
            const showNotification = options.showNotification !== false;
            const notify = isFunction(options.notify) ? options.notify : null;

            if (!normalized) {
                if (showNotification) {
                    this.#notify(errorMessage, 'error', notify);
                }
                options.onError?.(new Error('Clipboard requires non-empty text'));
                return false;
            }

            if (!this.isSupported()) {
                if (showNotification) {
                    this.#notify(unavailableMessage, 'error', notify);
                }
                options.onError?.(new Error('Clipboard API unavailable'));
                return false;
            }

            if (this.#isSecureClipboardSupported()) {
                const clipboard = this.scope.navigator?.clipboard;
                if (!clipboard || !isFunction(clipboard.writeText)) {
                    throw new Error('Secure clipboard API is unavailable');
                }
                await clipboard.writeText(normalized);
            } else {
                const ok = this.#writeViaHttpDom(normalized);
                if (!ok) {
                    throw new Error('HTTP clipboard copy failed');
                }
            }
            if (showNotification) {
                this.#notify(successMessage, 'copy', notify);
            }
            options.onSuccess?.();
            return true;
        } catch (error) {
            const err = ensureError(error);
            errorHandler.error('ClipboardService', 'Copy operation failed', err);
            const errorMessage = options.errorMessage ?? i18n.t('common.clipboard.copyFailed');
            const showNotification = options.showNotification !== false;
            const notify = isFunction(options.notify) ? options.notify : null;
            if (showNotification) {
                this.#notify(errorMessage, 'error', notify);
            }
            options.onError?.(ensureError(error));
            throw ensureError(error);
        }
    }

    #writeViaHttpDom(text: string): boolean {
        const doc = this.scope?.document;
        if (!doc?.body) {
            return false;
        }
        const node = doc.createElement('textarea');
        node.value = text;
        node.setAttribute('readonly', 'readonly');
        node.style.position = 'fixed';
        node.style.opacity = '0';
        node.style.pointerEvents = 'none';
        doc.body.appendChild(node);
        node.focus();
        node.select();
        node.setSelectionRange(0, node.value.length);
        const result = doc.execCommand('copy');
        doc.body.removeChild(node);
        return Boolean(result);
    }
}

let clipboardServiceInstance: ClipboardService | null = null;

const getClipboardService = (): ClipboardService => {
    if (!clipboardServiceInstance) {
        clipboardServiceInstance = new ClipboardService();
    }
    return clipboardServiceInstance;
};

const registerClipboardNotificationHandler = (handler: NotificationHandler): (() => void) => getClipboardService().registerNotificationHandler(handler);

const copyText = (text: ClipboardCopyInput, options: CopyOptions = {}): Promise<boolean> => getClipboardService().copyText(text, options);

const isClipboardSupported = (): boolean => getClipboardService().isSupported();

export { ClipboardService, copyText, getClipboardService, isClipboardSupported, registerClipboardNotificationHandler };
export type { ClipboardCopyInput, CopyOptions };
