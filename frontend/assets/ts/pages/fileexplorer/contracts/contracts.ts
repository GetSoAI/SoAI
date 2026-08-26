/* SoAI - File Explorer header control contracts [frontend/assets/ts/pages/fileexplorer/contracts/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type FileExplorerNewEntryValue = 'folder' | 'file' | 'uploadFiles' | 'uploadFolder';

type FileExplorerNewEntryOptionValue = FileExplorerNewEntryValue | '';

const FILE_EXPLORER_NEW_ENTRY_OPTION_VALUES: readonly FileExplorerNewEntryOptionValue[] = ['', 'folder', 'file', 'uploadFiles', 'uploadFolder'];

const FILE_EXPLORER_SEARCH_CONTAINER_ID = 'fileExplorer-search-container';

const FILE_EXPLORER_SEARCH_CONTAINER_SELECTOR = `#${FILE_EXPLORER_SEARCH_CONTAINER_ID}`;

const isFileExplorerNewEntryValue = (value: string): value is FileExplorerNewEntryValue => value === 'folder' || value === 'file' || value === 'uploadFiles' || value === 'uploadFolder';

export { FILE_EXPLORER_NEW_ENTRY_OPTION_VALUES, FILE_EXPLORER_SEARCH_CONTAINER_ID, FILE_EXPLORER_SEARCH_CONTAINER_SELECTOR, isFileExplorerNewEntryValue };
export type { FileExplorerNewEntryOptionValue, FileExplorerNewEntryValue };
