/* SoAI - Shared clipboard copy feedback helpers [frontend/assets/ts/core/ui/notifications/clipboardCopy.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { copyText, isClipboardSupported } from '@core/clipboard.ts';
import { toTrimmedString } from '@core/normalize.ts';
import type { NotificationType } from '@core/ui/notifications/types.ts';

interface ClipboardNotificationHost {
    showNotification: (message: string, type: NotificationType, duration?: number) => void;
}

interface ClipboardCopyRunner {
    copyToClipboard: (text: string, options?: { notify?: (message: string, type: string) => void }) => Promise<boolean | void>;
    hasClipboardSupport?: (() => boolean) | undefined;
}

interface ClipboardCopyAdapterHost extends ClipboardNotificationHost {
    copyToClipboard: (text: string, options?: { notify?: (message: string, type: NotificationType) => void }) => Promise<boolean | void>;
    hasClipboardSupport: () => boolean;
}

interface ClipboardCopyNotificationOptions {
    successMessage: string;
    errorMessage?: string | null | undefined;
    duration?: number | undefined;
    blurElement?: HTMLElement | null | undefined;
}

interface ClipboardCopyFeedbackOptions extends ClipboardCopyNotificationOptions {
    text: string;
    unavailableMessage?: string | null | undefined;
    unavailableType?: Extract<NotificationType, 'warning' | 'error'> | undefined;
    preserveText?: boolean | undefined;
}

const normalizeClipboardNotificationType = (value: string): NotificationType => {
    const normalized = toTrimmedString(value).toLowerCase();
    if (normalized === 'success' || normalized === 'info' || normalized === 'warning' || normalized === 'danger' || normalized === 'error' || normalized === 'copy' || normalized === 'refresh' || normalized === 'download') {
        return normalized;
    }
    return 'error';
};

const createClipboardCopyNotificationHandler = (host: ClipboardNotificationHost, options: ClipboardCopyNotificationOptions): ((message: string, type: string) => void) => {
    return (message: string, type: string): void => {
        const notificationType = normalizeClipboardNotificationType(type);
        if (notificationType === 'copy') {
            host.showNotification(options.successMessage, 'copy', options.duration);
            options.blurElement?.blur();
            return;
        }
        const errorMessage = toTrimmedString(options.errorMessage);
        host.showNotification(errorMessage || toTrimmedString(message) || i18n.t('common.clipboard.copyFailed'), 'error', options.duration);
    };
};

const copyTextWithClipboardFeedback = async (runner: ClipboardCopyRunner, host: ClipboardNotificationHost, options: ClipboardCopyFeedbackOptions): Promise<boolean> => {
    const text = options.preserveText === true ? options.text : toTrimmedString(options.text);
    if (!text) {
        host.showNotification(toTrimmedString(options.errorMessage) || i18n.t('common.clipboard.copyFailed'), 'error', options.duration);
        return false;
    }
    if (runner.hasClipboardSupport?.() === false) {
        host.showNotification(toTrimmedString(options.unavailableMessage) || i18n.t('common.clipboard.copyUnavailable'), options.unavailableType ?? 'warning', options.duration);
        return false;
    }
    const copied = await runner.copyToClipboard(text, {
        notify: createClipboardCopyNotificationHandler(host, options)
    });
    if (copied === false) {
        return false;
    }
    return true;
};

const copyTextWithHostClipboardFeedback = async (host: ClipboardCopyAdapterHost, options: ClipboardCopyFeedbackOptions): Promise<boolean> => {
    return await copyTextWithClipboardFeedback(
        {
            copyToClipboard: async (text, copyOptions): Promise<boolean | void> =>
                await host.copyToClipboard(
                    text,
                    copyOptions?.notify
                        ? {
                              notify: (message: string, type: string): void => copyOptions.notify?.(message, normalizeClipboardNotificationType(type))
                          }
                        : undefined
                ),
            hasClipboardSupport: () => host.hasClipboardSupport()
        },
        {
            showNotification: (message, type, duration): void => host.showNotification(message, type, duration)
        },
        options
    );
};

const copyTextWithBrowserClipboardFeedback = async (host: ClipboardNotificationHost, options: ClipboardCopyFeedbackOptions): Promise<boolean> => {
    return await copyTextWithClipboardFeedback(
        {
            copyToClipboard: async (text, copyOptions): Promise<boolean | void> => await copyText(text, copyOptions?.notify ? { notify: copyOptions.notify } : undefined),
            hasClipboardSupport: () => isClipboardSupported()
        },
        host,
        options
    );
};

export { copyTextWithBrowserClipboardFeedback, copyTextWithClipboardFeedback, copyTextWithHostClipboardFeedback, normalizeClipboardNotificationType };
