/* SoAI - File explorer page control layer operations [frontend/assets/ts/pages/fileexplorer/controllers/fileExplorerOperations.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toVirtualPath } from '@core/fileexplorerbrowser/paths.ts';
import { requirePathLeaf } from '@core/filePathResolution.ts';

type FileExplorerRenameLeafError = 'invalid' | 'pathSeparator' | 'required' | 'unchanged';

const FORBIDDEN_RENAME_LEAF_CHARACTERS: readonly string[] = [':', '*', '?', '"', '<', '>', '|'];
const RESERVED_WINDOWS_RENAME_LEAF_PATTERN = /^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?$/i;

const toFiles = (files: FileList): File[] => {
    const list = Array.from(files);
    if (list.length <= 0) {
        throw new Error('fileExplorer.upload requires at least one file');
    }
    return list;
};

const filenameFromPath = (path: string): string => {
    return requirePathLeaf(toVirtualPath(path), 'fileExplorer.path filename is required');
};

const normalizeFileExplorerRenameLeaf = (value: string): string => value.trim();

const validateFileExplorerRenameLeaf = (value: string, currentLeaf: string): FileExplorerRenameLeafError | null => {
    const normalized = normalizeFileExplorerRenameLeaf(value);
    if (!normalized) {
        return 'required';
    }
    if (value === currentLeaf || normalized === currentLeaf) {
        return 'unchanged';
    }
    if (normalized.includes('/') || normalized.includes('\\')) {
        return 'pathSeparator';
    }
    if (normalized.includes('\x00') || normalized === '.' || normalized === '..') {
        return 'invalid';
    }
    if (normalized.endsWith('.') || RESERVED_WINDOWS_RENAME_LEAF_PATTERN.test(normalized)) {
        return 'invalid';
    }
    if (FORBIDDEN_RENAME_LEAF_CHARACTERS.some((character) => normalized.includes(character))) {
        return 'invalid';
    }
    return null;
};

export { filenameFromPath, normalizeFileExplorerRenameLeaf, toFiles, validateFileExplorerRenameLeaf };
export type { FileExplorerRenameLeafError };
