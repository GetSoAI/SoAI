/* SoAI - File explorer entry name resolution [frontend/assets/ts/core/fileexplorerbrowser/entryNameResolution.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { FileBrowserRecord } from '@core/fileexplorerbrowser/types.ts';

interface FileEntryNameResolution {
    lowerName: string;
    lowerStem: string;
    extension: string;
    mimeType: string;
    mimeFamily: string;
}

const normalizeName = (name: string): string => name.trim();

const resolveExtensionStart = (name: string): number => {
    const dotIndex = name.lastIndexOf('.');
    if (dotIndex <= 0 || dotIndex === name.length - 1) {
        return -1;
    }
    return dotIndex;
};

const normalizeMimeType = (mimeType: string): string => mimeType.trim().toLowerCase();

const resolveMimeFamily = (mimeType: string): string => {
    const slashIndex = mimeType.indexOf('/');
    if (slashIndex <= 0) {
        return '';
    }
    return mimeType.slice(0, slashIndex);
};

const resolveFileEntryName = (entry: FileBrowserRecord): FileEntryNameResolution => {
    const normalizedName = normalizeName(entry.name);
    const lowerName = normalizedName.toLowerCase();
    const extensionStart = resolveExtensionStart(normalizedName);
    const extension = extensionStart >= 0 ? normalizedName.slice(extensionStart).toLowerCase() : '';
    const stem = extensionStart >= 0 ? normalizedName.slice(0, extensionStart) : normalizedName;
    const mimeType = normalizeMimeType(entry.mimeType);
    return {
        lowerName,
        lowerStem: stem.toLowerCase(),
        extension,
        mimeType,
        mimeFamily: resolveMimeFamily(mimeType)
    };
};

export { resolveFileEntryName };
export type { FileEntryNameResolution };
