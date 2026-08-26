/* SoAI - File explorer entry type mappings [frontend/assets/ts/core/fileexplorerbrowser/entryTypeMappings.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type FileEntryTypeId = 'archive' | 'audio' | 'binary' | 'code' | 'config' | 'database' | 'data' | 'directory' | 'document' | 'image' | 'jpegImage' | 'json' | 'markdown' | 'model' | 'pdf' | 'plugin' | 'pngImage' | 'presentation' | 'shellScript' | 'spreadsheet' | 'text' | 'unknownFile' | 'video';

const FILE_ENTRY_TYPE_IDS: readonly FileEntryTypeId[] = ['archive', 'audio', 'binary', 'code', 'config', 'database', 'data', 'directory', 'document', 'image', 'jpegImage', 'json', 'markdown', 'model', 'pdf', 'plugin', 'pngImage', 'presentation', 'shellScript', 'spreadsheet', 'text', 'unknownFile', 'video'];

const isFileEntryTypeId = (value: string): value is FileEntryTypeId => FILE_ENTRY_TYPE_IDS.some((typeId) => typeId === value);

export { isFileEntryTypeId };
export type { FileEntryTypeId };
