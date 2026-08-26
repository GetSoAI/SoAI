/* SoAI - File explorer content preview transfer actions [frontend/assets/ts/pages/fileexplorer/controllers/FileExplorerContentPreviewTransferController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { basenameVirtualPath, toVirtualPath } from '@core/fileexplorerbrowser/paths.ts';
import { i18n } from '@core/i18n/index.ts';
import { buildSoaiPathToken } from '@core/soailinks/codec.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import { copyTextWithBrowserClipboardFeedback } from '@core/ui/notifications/clipboardCopy.ts';

type FileExplorerContentPreviewTransferHost = Readonly<{
    downloadPath: (path: string) => Promise<void>;
    showNotification: (message: string, type: NotificationType) => void;
}>;

const downloadFileExplorerContentPreviewPath = async (host: FileExplorerContentPreviewTransferHost, path: string): Promise<void> => {
    await host.downloadPath(path);
};

const copyFileExplorerContentPreviewText = async (host: FileExplorerContentPreviewTransferHost, text: string): Promise<void> => {
    await copyTextWithBrowserClipboardFeedback(
        {
            showNotification: (message, type): void => host.showNotification(message, type)
        },
        {
            text,
            successMessage: i18n.t('fileExplorer.modal.copySuccess'),
            errorMessage: i18n.t('fileExplorer.modal.copyFailed'),
            unavailableMessage: i18n.t('fileExplorer.modal.copyFailed'),
            unavailableType: 'error'
        }
    );
};

const copyFileExplorerContentPreviewSoaiLink = async (host: FileExplorerContentPreviewTransferHost, path: string | null): Promise<void> => {
    if (!path) {
        throw new Error('File content preview modal cannot copy a SoAI link before a file is opened');
    }
    const virtualPath = toVirtualPath(path);
    await copyTextWithBrowserClipboardFeedback(
        {
            showNotification: (message, type): void => host.showNotification(message, type)
        },
        {
            text: buildSoaiPathToken({ virtualPath, label: basenameVirtualPath(virtualPath) }),
            successMessage: i18n.t('fileExplorer.modal.soaiLinkCopySuccess'),
            errorMessage: i18n.t('fileExplorer.modal.soaiLinkCopyFailed'),
            unavailableMessage: i18n.t('fileExplorer.modal.soaiLinkCopyFailed'),
            unavailableType: 'error'
        }
    );
};

const FileExplorerContentPreviewTransferController = Object.freeze({
    copyFileExplorerContentPreviewSoaiLink,
    copyFileExplorerContentPreviewText,
    downloadFileExplorerContentPreviewPath
});

export { FileExplorerContentPreviewTransferController };
export { copyFileExplorerContentPreviewSoaiLink, copyFileExplorerContentPreviewText, downloadFileExplorerContentPreviewPath };
export type { FileExplorerContentPreviewTransferHost };
