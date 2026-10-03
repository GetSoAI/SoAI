/* SoAI - File Explorer metadata markup rendering [frontend/assets/ts/pages/fileexplorer/rendering/FileExplorerMetadataMarkupWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveFileEntryTypeLabel } from '@core/fileexplorerbrowser/entryTypeLabels.ts';
import type { FileBrowserMetadata } from '@core/fileexplorerbrowser/types.ts';
import { i18n } from '@core/i18n/index.ts';
import { formatBytes } from '@core/primitives/byteSize.ts';
import { securityApi } from '@core/security/public.ts';

const renderMetadataMarkup = (metadata: FileBrowserMetadata): string => {
    const typeLabel = resolveFileEntryTypeLabel(metadata.typeId);
    return `
        <div class="file-explorer-metadata-row"><span>${i18n.t('fileExplorer.labels.path')}</span><bdi dir="ltr">${securityApi.escapeHtml(metadata.path)}</bdi></div>
        <div class="file-explorer-metadata-row"><span>${i18n.t('fileExplorer.table.type')}</span><span>${securityApi.escapeHtml(typeLabel)}</span></div>
        <div class="file-explorer-metadata-row"><span>${i18n.t('fileExplorer.table.size')}</span><bdi dir="ltr">${securityApi.escapeHtml(formatBytes(metadata.size, 1))}</bdi></div>
        <div class="file-explorer-metadata-row"><span>${i18n.t('fileExplorer.table.modified')}</span><bdi dir="ltr">${securityApi.escapeHtml(metadata.modifiedAt)}</bdi></div>
        <div class="file-explorer-metadata-row"><span>${i18n.t('fileExplorer.labels.permissions')}</span><bdi dir="ltr">${securityApi.escapeHtml(metadata.permissions)}</bdi></div>
        <div class="file-explorer-metadata-row"><span>${i18n.t('fileExplorer.labels.mime_type')}</span><bdi dir="ltr">${securityApi.escapeHtml(metadata.mimeType)}</bdi></div>
        <div class="file-explorer-metadata-row"><span>${i18n.t('fileExplorer.labels.sha256')}</span><bdi dir="ltr">${metadata.sha256 !== null ? securityApi.escapeHtml(metadata.sha256) : '-'}</bdi></div>
    `;
};

export { renderMetadataMarkup };
