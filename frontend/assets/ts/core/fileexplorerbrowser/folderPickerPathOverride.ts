/* SoAI - Folder picker path override normalization [frontend/assets/ts/core/fileexplorerbrowser/folderPickerPathOverride.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { FolderPickerResult } from '@core/fileexplorerbrowser/folderPickerModal.ts';

const resolveFolderPickerPathOverride = (result: FolderPickerResult): string | null | undefined => {
    if (result.resultType !== 'selected') {
        return undefined;
    }
    if (result.workspacePathResolved === null && result.absolutePath !== null) {
        return result.absolutePath.trim() ? result.absolutePath : undefined;
    }
    if (!result.virtualPath.trim()) {
        return undefined;
    }
    if (result.virtualPath === '.' || result.virtualPath === '/') {
        return null;
    }
    return result.virtualPath;
};

export { resolveFolderPickerPathOverride };
