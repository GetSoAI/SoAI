/* SoAI - Shared file explorer browser folder picker view [frontend/assets/ts/core/fileexplorerbrowser/folderPickerView.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveFileExplorerBrowserStatusMessage } from '@core/fileexplorerbrowser/errorMessages.ts';
import { i18n } from '@core/i18n/index.ts';
import { getLanguageService } from '@core/languageservice/service.ts';
import { parentVirtualPath, resolveAbsolutePath } from '@core/fileexplorerbrowser/paths.ts';
import type { FileBrowserEntry } from '@core/fileexplorerbrowser/types.ts';
import { renderModalFooterActionButton, renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import { modalUiId } from '@core/modals/uiIds.ts';

import { securityApi, type TrustedHtml } from '@core/security/public.ts';
import { EMPTY_UI_HTML, uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { renderSearchFieldActions } from '@core/ui/searchField.ts';

interface FolderPickerLabels {
    currentFolder: string;
    filesystemRoot: string;
    manualPath: string;
    manualAbsolutePathRequired: string;
    loadFailed: string;
    validationFailed: string;
    search: string;
    searchPlaceholder: string;
    loading: string;
    searching: string;
    empty: string;
    up: string;
    chooseCurrent: string;
    cancel: string;
    reset?: string;
}

const resolveBrowserErrorMessage = (error: Error): string => {
    return resolveFileExplorerBrowserStatusMessage(error, {
        forbidden: (): string => i18n.t('common.folderPicker.forbidden'),
        missing: (): string => i18n.t('common.folderPicker.notFound'),
        precondition: (): string => i18n.t('common.folderPicker.loadFailed'),
        unprocessable: (message: string): string => message,
        fallback: (): string => i18n.t('common.folderPicker.loadFailed')
    });
};

const sortEntriesByName = <T extends { name: string }>(entries: readonly T[], direction: 'asc' | 'desc'): readonly T[] => {
    const multiplier = direction === 'asc' ? 1 : -1;
    return [...entries].sort((firstValue, secondValue) => multiplier * firstValue.name.localeCompare(secondValue.name, getLanguageService().getLocale(), { sensitivity: 'base' }));
};

const formatDisplayPath = (virtualPath: string, workspacePathResolved: string | null): string => {
    const absolutePath = resolveAbsolutePath(workspacePathResolved, virtualPath);
    return absolutePath ?? virtualPath;
};

type GetIconSync = (iconName: IconName, options?: IconOptions) => TrustedHtml;

const renderFolderRows = (entries: readonly FileBrowserEntry[], currentPath: string, labels: FolderPickerLabels, getIconSync: GetIconSync): string => {
    const folderIcon = getIconSync('folder', { size: 16, strokeWidth: 1.5 }).html;
    const upIcon = getIconSync('chevron-up', { size: 16, strokeWidth: 1.5 }).html;
    const renderRow = (inputArguments: { action: 'folder-picker-open' | 'folder-picker-up'; path: string; label: string; ariaLabel: string; iconHtml: string }): string => {
        const escapedPath = securityApi.escapeAttribute(inputArguments.path);
        const escapedAriaLabel = securityApi.escapeAttribute(inputArguments.ariaLabel);
        return `<tr><td class="folder-picker-name-cell"><button type="button" class="folder-picker-open-btn" data-action="${inputArguments.action}" data-path="${escapedPath}" aria-label="${escapedAriaLabel}" data-tooltip="${escapedAriaLabel}"><span class="folder-picker-entry-icon" aria-hidden="true">${inputArguments.iconHtml}</span>${securityApi.escapeHtml(inputArguments.label)}</button></td></tr>`;
    };

    const parentRow = currentPath === '/' ? '' : renderRow({ action: 'folder-picker-up', path: parentVirtualPath(currentPath), label: '..', ariaLabel: labels.up, iconHtml: upIcon });
    const rows = entries.map((entry) => renderRow({ action: 'folder-picker-open', path: entry.path, label: entry.name, ariaLabel: entry.name, iconHtml: folderIcon })).join('');
    if (!parentRow && !rows) {
        return `<tr><td class="folder-picker-empty-row">${securityApi.escapeHtml(labels.empty)}</td></tr>`;
    }
    return parentRow + rows;
};

const resolveFolderPickerStatusText = (state: { isLoading: boolean; errorMessage: string | null; query: string }, labels: FolderPickerLabels, overrideMessage: string | null): string => {
    if (overrideMessage) {
        return overrideMessage;
    }
    if (state.errorMessage) {
        return state.errorMessage;
    }
    if (!state.isLoading) {
        return '';
    }
    return state.query.trim() ? labels.searching : labels.loading;
};

const renderFolderPickerInitialStatus = (labels: FolderPickerLabels): TrustedHtml => {
    return uiHtml`<span class="loading-spinner inline-loading-status-spinner" aria-hidden="true"></span><span class="inline-loading-status-text">${labels.loading}</span>`;
};

const renderFolderPickerManualInput = (modalId: string, labels: FolderPickerLabels, editable: boolean): TrustedHtml => {
    const readonlyAttributes = editable ? EMPTY_UI_HTML : uiHtml` readonly aria-readonly="true"`;
    return uiHtml`<div class="form-group folder-picker-manual-group"><label for="${uiAttr(modalUiId(modalId, 'manual'))}">${labels.manualPath}</label><input id="${uiAttr(modalUiId(modalId, 'manual'))}" class="form-input" type="text" value=""${readonlyAttributes}></div>`;
};

const renderFolderPickerResetButton = (labels: FolderPickerLabels, modalId: string): TrustedHtml => {
    if (!labels.reset) {
        return EMPTY_UI_HTML;
    }
    return renderModalFooterActionButton({ id: modalUiId(modalId, 'reset'), text: labels.reset });
};

const renderFolderPickerModalMarkup = (options: { modalId: string; labels: FolderPickerLabels; nameColumnLabel: string; allowManualPathEntry?: boolean; hostMode: boolean }): { body: TrustedHtml; footerLeft: TrustedHtml; footerRight: TrustedHtml } => {
    const manualInputMarkup = renderFolderPickerManualInput(options.modalId, options.labels, options.allowManualPathEntry === true);
    const resetButtonMarkup = renderFolderPickerResetButton(options.labels, options.modalId);
    const footerLeft = uiHtml`${renderModalFooterCloseButton({ modalId: options.modalId, id: modalUiId(options.modalId, 'cancel'), text: options.labels.cancel })}${resetButtonMarkup}`;
    const footerRight = renderModalFooterActionButton({ id: modalUiId(options.modalId, 'confirm'), text: options.labels.chooseCurrent, variant: 'accent' });
    const rootSelector = options.hostMode ? uiHtml`<div class="form-col-side"><label for="${uiAttr(modalUiId(options.modalId, 'root'))}">${options.labels.filesystemRoot}</label><select id="${uiAttr(modalUiId(options.modalId, 'root'))}" class="form-input"></select></div>` : EMPTY_UI_HTML;

    const body = uiHtml`
        <div class="folder-picker-panel">
            <div class="folder-picker-toolbar">
                <div class="form-row-split manual-path-row folder-picker-current">
                    <div class="form-col-main">
                        <label for="${uiAttr(modalUiId(options.modalId, 'current'))}">${options.labels.currentFolder}</label>
                        <input id="${uiAttr(modalUiId(options.modalId, 'current'))}" class="form-input manual-models-path folder-picker-current-path" type="text" value="" readonly spellcheck="false" autocapitalize="off" autocomplete="off">
                    </div>
                    ${rootSelector}
                </div>
            </div>
            ${manualInputMarkup}
            <div class="form-group folder-picker-search-group">
                <label for="${uiAttr(modalUiId(options.modalId, 'search'))}">${options.labels.search}</label>
                <div class="searchbar-container searchbar-container--collection folder-picker-searchbar">
                    <input id="${uiAttr(modalUiId(options.modalId, 'search'))}" class="form-input searchbar-input" type="search" placeholder="${uiAttr(options.labels.searchPlaceholder)}">
                    ${renderSearchFieldActions()}
                </div>
            </div>
            <div class="folder-picker-status-slot">
                <div id="${uiAttr(modalUiId(options.modalId, 'status'))}" class="chat-configuration-hint folder-picker-status inline-loading-status is-loading">${renderFolderPickerInitialStatus(options.labels)}</div>
            </div>
            <div class="folder-picker-table-scope">
                <div class="data-table-wrapper folder-picker-table-wrap">
                    <table id="${uiAttr(modalUiId(options.modalId, 'table'))}" class="table-compact folder-picker-table">
                        <thead>
                            <tr>
                                <th id="${uiAttr(modalUiId(options.modalId, 'sort-name'))}" class="sortable is-active" data-action="folder-picker-sort" data-sort="name" tabindex="0" role="columnheader" aria-sort="ascending">${options.nameColumnLabel} <span class="sort-indicator"></span></th>
                            </tr>
                        </thead>
                        <tbody id="${uiAttr(modalUiId(options.modalId, 'rows'))}" class="folder-picker-rows-body">
                            <tr><td class="folder-picker-empty-row">${options.labels.loading}</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    `;

    return { body, footerLeft, footerRight };
};

export { formatDisplayPath, renderFolderPickerManualInput, renderFolderPickerModalMarkup, renderFolderPickerResetButton, renderFolderRows, resolveBrowserErrorMessage, resolveFolderPickerStatusText, sortEntriesByName };
export type { FolderPickerLabels };
