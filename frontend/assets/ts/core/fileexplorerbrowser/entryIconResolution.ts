/* SoAI - File explorer entry icon resolution [frontend/assets/ts/core/fileexplorerbrowser/entryIconResolution.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveExactFileEntryIconName, resolveExtensionFileEntryIconName } from '@core/fileexplorerbrowser/entryIconMappings.ts';
import { resolveFileEntryName } from '@core/fileexplorerbrowser/entryNameResolution.ts';
import type { FileBrowserRecord } from '@core/fileexplorerbrowser/types.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';

const FOLDER_ICON: IconName = 'folder';
const DEFAULT_FILE_ICON: IconName = 'file-generic';

const resolveFileEntryIconName = (entry: FileBrowserRecord): IconName => {
    if (entry.isDirectory) {
        return FOLDER_ICON;
    }
    const name = resolveFileEntryName(entry);
    const exact = resolveExactFileEntryIconName(name.lowerName);
    if (exact !== null) {
        return exact;
    }
    const extension = resolveExtensionFileEntryIconName(name.extension);
    return extension ?? DEFAULT_FILE_ICON;
};

export { resolveFileEntryIconName };
