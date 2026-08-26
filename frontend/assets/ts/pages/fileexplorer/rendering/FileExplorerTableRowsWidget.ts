/* SoAI - File Explorer table row rendering [frontend/assets/ts/pages/fileexplorer/rendering/FileExplorerTableRowsWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveFileEntryIconName } from '@core/fileexplorerbrowser/entryIconResolution.ts';
import { resolveInputList } from '@core/dom/typedElementResolver.ts';
import { resolveFileEntryTypeLabel, resolveFileEntryTypeShortLabel } from '@core/fileexplorerbrowser/entryTypeLabels.ts';
import type { FileBrowserEntry } from '@core/fileexplorerbrowser/types.ts';
import { i18n } from '@core/i18n/index.ts';
import { formatBytes } from '@core/primitives/byteSize.ts';
import { renderLabelAttributes, type TrustedHtml } from '@core/security/public.ts';
import { uiAttr, uiAttributes, uiHtml, uiText } from '@core/security/uiHtml.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import { FILE_EXPLORER_ACTION_CLEAR_HIGHLIGHT, FILE_EXPLORER_ACTION_ROW_OPEN, FILE_EXPLORER_ACTION_SELECT_ROW } from '@features/fileexplorer/public.ts';

type GetIconSync = (iconName: IconName, options?: IconOptions) => TrustedHtml;
type IsRecentEntry = (entry: FileBrowserEntry) => boolean;

const renderFileExplorerEntryRowMarkup = (entry: FileBrowserEntry, getIconSync: GetIconSync, isRecentEntry: IsRecentEntry): TrustedHtml => {
    const rowAttributes = uiAttributes({ class: isRecentEntry(entry) ? 'session-recent-row' : undefined });
    const typeLabel = resolveFileEntryTypeLabel(entry.typeId);
    const typeCellContent = uiHtml`<span class="file-explorer-type-label file-explorer-type-label--full">${uiText(typeLabel)}</span><span class="file-explorer-type-label file-explorer-type-label--short" aria-hidden="true">${uiText(resolveFileEntryTypeShortLabel(entry.typeId))}</span>`;
    const sizeLabel = entry.isDirectory ? '-' : formatBytes(entry.size, 1);
    const sizeCellClass = entry.isDirectory ? 'file-explorer-meta-cell file-explorer-meta-cell--directory-size' : 'file-explorer-meta-cell';
    const iconName = resolveFileEntryIconName(entry);
    const iconMarkup = getIconSync(iconName, { size: 16, strokeWidth: 1.5 });
    return uiHtml`<tr${rowAttributes} data-action="${uiAttr(FILE_EXPLORER_ACTION_ROW_OPEN)}" data-path="${uiAttr(entry.path)}" data-directory="${uiAttr(entry.isDirectory ? '1' : '0')}">
	        <td><input type="checkbox" data-action="${uiAttr(FILE_EXPLORER_ACTION_SELECT_ROW)}" data-path="${uiAttr(entry.path)}"></td>
	        <td class="file-explorer-name-cell"><button type="button" class="file-explorer-open-btn"${renderLabelAttributes({ ariaLabel: entry.name, tooltip: entry.path })}><span class="file-explorer-entry-icon" aria-hidden="true">${iconMarkup}<span class="loading-spinner file-explorer-entry-open-spinner"></span></span><span class="file-explorer-entry-name">${uiText(entry.name)}</span></button></td>
	        <td class="file-explorer-meta-cell file-explorer-meta-cell--type" aria-label="${uiAttr(typeLabel)}">${typeCellContent}</td>
        <td class="${uiAttr(sizeCellClass)}">${uiText(sizeLabel)}</td>
        <td class="file-explorer-meta-cell">${uiText(entry.modifiedAt)}</td>
	    </tr>`;
};

const renderFileExplorerParentRowMarkup = (parentPathValue: string, getIconSync: GetIconSync): TrustedHtml => {
    const upLabel = i18n.t('fileExplorer.actions.parent');
    const iconList = renderIconSlot(getIconSync('chevron-up', { size: 16, strokeWidth: 1.5 }));
    const iconIcons = renderIconSlot(getIconSync('chevron-left', { size: 16, strokeWidth: 1.5 }));
    return uiHtml`<tr data-action="${uiAttr(FILE_EXPLORER_ACTION_ROW_OPEN)}" data-path="${uiAttr(parentPathValue)}" data-directory="1" data-parent-row="1">
	        <td class="file-explorer-parent-icon-cell"><button type="button" class="file-explorer-open-btn"${renderLabelAttributes(upLabel)}><span class="file-explorer-parent-icon-list">${iconList}</span><span class="file-explorer-parent-icon-icons">${iconIcons}</span></button></td>
	        <td class="file-explorer-name-cell"><button type="button" class="file-explorer-open-btn file-explorer-parent-open-btn"${renderLabelAttributes(upLabel)}><span class="file-explorer-parent-label-compact" aria-hidden="true">..</span><span class="file-explorer-parent-label">${uiText(upLabel)}</span></button></td>
	        <td></td><td></td><td></td>
	    </tr>`;
};

const renderFileExplorerEmptyRowMarkup = (): TrustedHtml => uiHtml`<tr><td colspan="5" class="file-explorer-empty-row" data-action="${FILE_EXPLORER_ACTION_CLEAR_HIGHLIGHT}">${i18n.t('fileExplorer.status.empty')}</td></tr>`;

const renderFileExplorerLoadingRowMarkup = (label: string): TrustedHtml => uiHtml`<tr><td colspan="5" class="file-explorer-empty-row file-explorer-loading-row"><span class="loading-spinner" aria-hidden="true"></span><span>${uiText(label)}</span></td></tr>`;

const syncRowSelectionControls = (rowsBody: HTMLElement, selectedPaths: ReadonlySet<string>): void => {
    const selector = `input[type="checkbox"][data-action="${FILE_EXPLORER_ACTION_SELECT_ROW}"]`;
    resolveInputList(selector, rowsBody, 'File Explorer row selection control').forEach((checkbox) => {
        const path = checkbox.dataset['path'];
        if (!path) {
            throw new Error('File Explorer row selection control requires a path');
        }
        checkbox.checked = selectedPaths.has(path);
    });
};

export { renderFileExplorerEmptyRowMarkup, renderFileExplorerEntryRowMarkup, renderFileExplorerLoadingRowMarkup, renderFileExplorerParentRowMarkup, syncRowSelectionControls };
