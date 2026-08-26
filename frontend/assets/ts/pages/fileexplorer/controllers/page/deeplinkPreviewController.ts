/* SoAI - File explorer page control layer deeplink preview controller [frontend/assets/ts/pages/fileexplorer/controllers/page/deeplinkPreviewController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toVirtualPath } from '@core/fileexplorerbrowser/paths.ts';

interface FileExplorerDeeplinkPreviewController {
    open: () => Promise<void>;
    clear: () => void;
}

interface FileExplorerDeeplinkPreviewDependencies {
    previewPath: string | null;
    isDisposed: () => boolean;
    openPreview: (path: string) => Promise<void>;
}

const normalizeOptionalVirtualPath = (value: string | null): string | null => {
    if (!value) {
        return null;
    }
    const trimmed = value.trim();
    return trimmed ? toVirtualPath(trimmed) : null;
};

const createFileExplorerDeeplinkPreviewController = (dependencies: FileExplorerDeeplinkPreviewDependencies): FileExplorerDeeplinkPreviewController => {
    let previewPath = normalizeOptionalVirtualPath(dependencies.previewPath);
    let sequence = 0;

    const clear = (): void => {
        previewPath = null;
        sequence += 1;
    };

    const open = async (): Promise<void> => {
        const targetPath = previewPath;
        if (!targetPath || dependencies.isDisposed()) {
            return;
        }
        const requestSequence = sequence + 1;
        sequence = requestSequence;
        if (dependencies.isDisposed() || sequence !== requestSequence) {
            return;
        }
        await dependencies.openPreview(targetPath);
    };

    return { open, clear };
};

export { createFileExplorerDeeplinkPreviewController };
export type { FileExplorerDeeplinkPreviewController };
