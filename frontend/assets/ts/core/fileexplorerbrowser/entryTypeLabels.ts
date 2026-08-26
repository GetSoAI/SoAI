/* SoAI - File explorer entry type translated labels [frontend/assets/ts/core/fileexplorerbrowser/entryTypeLabels.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { FileEntryTypeId } from '@core/fileexplorerbrowser/entryTypeMappings.ts';
import { i18n } from '@core/i18n/index.ts';

interface FileEntryTypeTranslations {
    label(): string;
    shortLabel(): string;
}

const FILE_ENTRY_TYPE_TRANSLATIONS: Readonly<Record<FileEntryTypeId, FileEntryTypeTranslations>> = {
    archive: { label: () => i18n.t('fileExplorer.entryTypes.archive'), shortLabel: () => i18n.t('fileExplorer.entryTypesShort.archive') },
    audio: { label: () => i18n.t('fileExplorer.entryTypes.audio'), shortLabel: () => i18n.t('fileExplorer.entryTypesShort.audio') },
    binary: { label: () => i18n.t('fileExplorer.entryTypes.binary'), shortLabel: () => i18n.t('fileExplorer.entryTypesShort.binary') },
    code: { label: () => i18n.t('fileExplorer.entryTypes.code'), shortLabel: () => i18n.t('fileExplorer.entryTypesShort.code') },
    config: { label: () => i18n.t('fileExplorer.entryTypes.config'), shortLabel: () => i18n.t('fileExplorer.entryTypesShort.config') },
    database: { label: () => i18n.t('fileExplorer.entryTypes.database'), shortLabel: () => i18n.t('fileExplorer.entryTypesShort.database') },
    data: { label: () => i18n.t('fileExplorer.entryTypes.data'), shortLabel: () => i18n.t('fileExplorer.entryTypesShort.data') },
    directory: { label: () => i18n.t('fileExplorer.entryTypes.directory'), shortLabel: () => i18n.t('fileExplorer.entryTypesShort.directory') },
    document: { label: () => i18n.t('fileExplorer.entryTypes.document'), shortLabel: () => i18n.t('fileExplorer.entryTypesShort.document') },
    image: { label: () => i18n.t('fileExplorer.entryTypes.image'), shortLabel: () => i18n.t('fileExplorer.entryTypesShort.image') },
    jpegImage: { label: () => i18n.t('fileExplorer.entryTypes.jpegImage'), shortLabel: () => i18n.t('fileExplorer.entryTypesShort.jpegImage') },
    json: { label: () => i18n.t('fileExplorer.entryTypes.json'), shortLabel: () => i18n.t('fileExplorer.entryTypesShort.json') },
    markdown: { label: () => i18n.t('fileExplorer.entryTypes.markdown'), shortLabel: () => i18n.t('fileExplorer.entryTypesShort.markdown') },
    model: { label: () => i18n.t('fileExplorer.entryTypes.model'), shortLabel: () => i18n.t('fileExplorer.entryTypesShort.model') },
    pdf: { label: () => i18n.t('fileExplorer.entryTypes.pdf'), shortLabel: () => i18n.t('fileExplorer.entryTypesShort.pdf') },
    plugin: { label: () => i18n.t('fileExplorer.entryTypes.plugin'), shortLabel: () => i18n.t('fileExplorer.entryTypesShort.plugin') },
    pngImage: { label: () => i18n.t('fileExplorer.entryTypes.pngImage'), shortLabel: () => i18n.t('fileExplorer.entryTypesShort.pngImage') },
    presentation: { label: () => i18n.t('fileExplorer.entryTypes.presentation'), shortLabel: () => i18n.t('fileExplorer.entryTypesShort.presentation') },
    shellScript: { label: () => i18n.t('fileExplorer.entryTypes.shellScript'), shortLabel: () => i18n.t('fileExplorer.entryTypesShort.shellScript') },
    spreadsheet: { label: () => i18n.t('fileExplorer.entryTypes.spreadsheet'), shortLabel: () => i18n.t('fileExplorer.entryTypesShort.spreadsheet') },
    text: { label: () => i18n.t('fileExplorer.entryTypes.text'), shortLabel: () => i18n.t('fileExplorer.entryTypesShort.text') },
    unknownFile: { label: () => i18n.t('fileExplorer.entryTypes.unknownFile'), shortLabel: () => i18n.t('fileExplorer.entryTypesShort.unknownFile') },
    video: { label: () => i18n.t('fileExplorer.entryTypes.video'), shortLabel: () => i18n.t('fileExplorer.entryTypesShort.video') }
};

const resolveFileEntryTypeLabel = (typeId: FileEntryTypeId): string => FILE_ENTRY_TYPE_TRANSLATIONS[typeId].label();

const resolveFileEntryTypeShortLabel = (typeId: FileEntryTypeId): string => FILE_ENTRY_TYPE_TRANSLATIONS[typeId].shortLabel();

export { resolveFileEntryTypeLabel, resolveFileEntryTypeShortLabel };
