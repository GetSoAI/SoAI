/* SoAI - File explorer entry icon resolution [frontend/assets/ts/core/fileexplorerbrowser/entryIconResolution.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveExactFileEntryIconName, resolveExtensionFileEntryIconName } from '@core/fileexplorerbrowser/entryIconMappings.ts';
import { resolveFileEntryName } from '@core/fileexplorerbrowser/entryNameResolution.ts';
import { classifyFileBrowserMimeType } from '@core/fileexplorerbrowser/mediaClassification.ts';
import type { FileBrowserMediaType, FileEntryIconDescriptor } from '@core/fileexplorerbrowser/types.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';

const FOLDER_ICON: IconName = 'folder';
const DEFAULT_FILE_ICON: IconName = 'file-generic';

const MIME_TYPE_ICON: Readonly<Record<FileBrowserMediaType, IconName>> = {
    image: 'file-image',
    audio: 'file-audio',
    video: 'file-video',
    text: 'file-text',
    document: 'file-document',
    file: DEFAULT_FILE_ICON
};

const resolveFileEntryIconName = (entry: FileEntryIconDescriptor): IconName => {
    if (entry.isDirectory) {
        return FOLDER_ICON;
    }
    const name = resolveFileEntryName(entry);
    const exact = resolveExactFileEntryIconName(name.lowerName);
    if (exact !== null) {
        return exact;
    }
    const extension = resolveExtensionFileEntryIconName(name.extension);
    if (extension !== null) {
        return extension;
    }
    return MIME_TYPE_ICON[classifyFileBrowserMimeType(name.mimeType)];
};

export { resolveFileEntryIconName };
