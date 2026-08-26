/* SoAI - File explorer content preview validation [frontend/assets/ts/pages/fileexplorer/controllers/FileExplorerContentPreviewValidationController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { filenameFromPath } from '@pages/fileexplorer/controllers/fileExplorerOperations.ts';
import type { ContentPreviewTextDraftSnapshot } from '@core/ui/modals/contentpreview/types.ts';

type ContentPreviewValidationArguments = Readonly<{
    path: string | null;
    baselineContent: string | null;
    isNewFile: boolean;
    isEditing: () => boolean;
    getDraftSnapshot: () => ContentPreviewTextDraftSnapshot | null;
}>;

class FileExplorerContentPreviewValidationController {
    static hasUnsavedChanges(inputArguments: ContentPreviewValidationArguments): boolean {
        const path = inputArguments.path;
        if (!path || !inputArguments.isEditing()) {
            return false;
        }
        const snapshot = inputArguments.getDraftSnapshot();
        if (!snapshot) {
            return false;
        }
        const baselineContent = inputArguments.baselineContent ?? '';
        const baselineFilename = filenameFromPath(path);
        const normalizedTitle = snapshot.title.trim();
        const requestedFilename = normalizedTitle ? filenameFromPath(normalizedTitle) : '';
        return inputArguments.isNewFile || snapshot.content !== baselineContent || requestedFilename !== baselineFilename;
    }

    static isPendingEditValid(inputArguments: Pick<ContentPreviewValidationArguments, 'isEditing' | 'getDraftSnapshot'>): boolean {
        if (!inputArguments.isEditing()) {
            return true;
        }
        const snapshot = inputArguments.getDraftSnapshot();
        if (!snapshot) {
            return false;
        }
        const normalizedTitle = snapshot.title.trim();
        return normalizedTitle ? filenameFromPath(normalizedTitle).length > 0 : false;
    }
}

export { FileExplorerContentPreviewValidationController };
