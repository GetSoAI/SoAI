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
        <div class="file-explorer-metadata-row"><span>${i18n.t('fileExplorer.labels.path')}</span><span>${securityApi.escapeHtml(metadata.path)}</span></div>
        <div class="file-explorer-metadata-row"><span>${i18n.t('fileExplorer.table.type')}</span><span>${securityApi.escapeHtml(typeLabel)}</span></div>
        <div class="file-explorer-metadata-row"><span>${i18n.t('fileExplorer.table.size')}</span><span>${securityApi.escapeHtml(formatBytes(metadata.size, 1))}</span></div>
        <div class="file-explorer-metadata-row"><span>${i18n.t('fileExplorer.table.modified')}</span><span>${securityApi.escapeHtml(metadata.modifiedAt)}</span></div>
        <div class="file-explorer-metadata-row"><span>${i18n.t('fileExplorer.labels.permissions')}</span><span>${securityApi.escapeHtml(metadata.permissions)}</span></div>
        <div class="file-explorer-metadata-row"><span>${i18n.t('fileExplorer.labels.mime_type')}</span><span>${securityApi.escapeHtml(metadata.mimeType)}</span></div>
        <div class="file-explorer-metadata-row"><span>${i18n.t('fileExplorer.labels.sha256')}</span><span>${metadata.sha256 !== null ? securityApi.escapeHtml(metadata.sha256) : '-'}</span></div>
    `;
};

export { renderMetadataMarkup };
