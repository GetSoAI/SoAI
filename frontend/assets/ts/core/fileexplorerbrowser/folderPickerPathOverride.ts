/* SoAI - Folder picker path override normalization [frontend/assets/ts/core/fileexplorerbrowser/folderPickerPathOverride.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { FolderPickerResult } from '@core/fileexplorerbrowser/folderPickerModal.ts';

const resolveFolderPickerPathOverride = (result: FolderPickerResult): string | null | undefined => {
    if (result.resultType !== 'selected') {
        return undefined;
    }
    if (result.workspacePathResolved === null && result.absolutePath !== null) {
        const trimmedAbsolutePath = result.absolutePath.trim();
        return trimmedAbsolutePath || undefined;
    }
    const trimmedVirtualPath = result.virtualPath.trim();
    if (!trimmedVirtualPath) {
        return undefined;
    }
    if (trimmedVirtualPath === '.' || trimmedVirtualPath === '/') {
        return null;
    }
    return trimmedVirtualPath;
};

export { resolveFolderPickerPathOverride };
