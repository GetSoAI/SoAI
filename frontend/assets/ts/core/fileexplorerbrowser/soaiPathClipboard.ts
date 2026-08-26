/* SoAI - File explorer SoAI path clipboard actions [frontend/assets/ts/core/fileexplorerbrowser/soaiPathClipboard.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { copyText, isClipboardSupported } from '@core/clipboard.ts';
import { basenameVirtualPath, toVirtualPath } from '@core/fileexplorerbrowser/paths.ts';
import { i18n } from '@core/i18n/index.ts';
import { buildSoaiPathToken } from '@core/soailinks/codec.ts';
import { copyTextWithHostClipboardFeedback } from '@core/ui/notifications/clipboardCopy.ts';
import { showNotification, type NotificationType } from '@core/ui/notifications/notifications.ts';

type SoaiPathClipboardHost = Readonly<{
    copyToClipboard: (text: string, options?: { notify?: (message: string, type: NotificationType) => void }) => Promise<void>;
    hasClipboardSupport: () => boolean;
    showNotification: (message: string, type: NotificationType) => void;
}>;

const createDefaultSoaiPathClipboardHost = (): SoaiPathClipboardHost =>
    Object.freeze({
        copyToClipboard: async (value, options): Promise<void> => {
            await copyText(value, options);
        },
        hasClipboardSupport: () => isClipboardSupported(),
        showNotification: (message, type): void => {
            showNotification(message, type);
        }
    });

const copySoaiPathLinkToClipboard = async (path: string, host: SoaiPathClipboardHost = createDefaultSoaiPathClipboardHost()): Promise<void> => {
    const virtualPath = toVirtualPath(path);
    const text = buildSoaiPathToken({ virtualPath, label: basenameVirtualPath(virtualPath) });
    await copySoaiPathTokenToClipboard(text, host);
};

const copySoaiPathTokenToClipboard = async (text: string, host: SoaiPathClipboardHost = createDefaultSoaiPathClipboardHost()): Promise<void> => {
    await copyTextWithHostClipboardFeedback(
        {
            copyToClipboard: async (value, options): Promise<void> => await host.copyToClipboard(value, options),
            hasClipboardSupport: () => host.hasClipboardSupport(),
            showNotification: (message, type): void => host.showNotification(message, type)
        },
        {
            text,
            successMessage: i18n.t('fileExplorer.modal.soaiLinkCopySuccess'),
            errorMessage: i18n.t('fileExplorer.modal.soaiLinkCopyFailed'),
            unavailableMessage: i18n.t('fileExplorer.modal.soaiLinkCopyFailed'),
            unavailableType: 'error'
        }
    );
};

export { copySoaiPathLinkToClipboard, copySoaiPathTokenToClipboard };
export type { SoaiPathClipboardHost };
