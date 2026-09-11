/* SoAI - Shared file explorer browser folder picker modal contracts [frontend/assets/ts/core/fileexplorerbrowser/folderPickerModalContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { FolderPickerLabels } from '@core/fileexplorerbrowser/folderPickerView.ts';
import type { FileBrowserSource } from '@core/fileexplorerbrowser/types.ts';

type FolderPickerResult = { resultType: 'selected'; virtualPath: string; absolutePath: string | null; workspacePathResolved: string | null } | { resultType: 'reset' };

interface FolderPickerModalOptions {
    source: FileBrowserSource;
    title: string;
    message: string;
    labels: FolderPickerLabels;
    initialVirtualPath?: string;
    initialAbsolutePathToBrowse?: string;
    allowManualPathEntry?: boolean;
}

export type { FolderPickerModalOptions, FolderPickerResult };
