/* SoAI - File explorer page DOM contracts [frontend/assets/ts/pages/fileexplorer/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireButtonElement, requireInputElement, requireSelectElement, requireTableSectionElement } from '@core/dom/typedElements.ts';
import type { FileExplorerUiRefs } from '@pages/fileexplorer/types.ts';

interface FileExplorerDomHost {
    requireHTMLElement: (selector: string, context?: Element | undefined) => HTMLElement;
    optionalHTMLElement: (selector: string, context?: Element | undefined) => HTMLElement | null;
}

const requireFileExplorerRoot = (host: FileExplorerDomHost): HTMLElement => host.requireHTMLElement('#file-explorer-root');

const requireFileExplorerUi = (host: FileExplorerDomHost): FileExplorerUiRefs => {
    return {
        root: requireFileExplorerRoot(host),
        breadcrumb: host.requireHTMLElement('#file-explorer-current-path'),
        currentPathInput: requireInputElement(host, '#file-explorer-current-path-input', 'File Explorer #file-explorer-current-path-input'),
        currentPathSaveButton: requireButtonElement(host, '.ui-inline-text-edit__save', 'File Explorer current path save button'),
        resultCount: host.requireHTMLElement('#file-explorer-result-count'),
        selectionCount: host.requireHTMLElement('#file-explorer-selection-count'),
        selectionStatusBadge: host.requireHTMLElement('#file-explorer-selection-status'),
        navigateHomeButton: requireButtonElement(host, '#file-explorer-navigate-home', 'File Explorer #file-explorer-navigate-home'),
        navigatePreviousButton: requireButtonElement(host, '#file-explorer-navigate-previous', 'File Explorer #file-explorer-navigate-previous'),
        navigateNextButton: requireButtonElement(host, '#file-explorer-navigate-next', 'File Explorer #file-explorer-navigate-next'),
        navigateUpButton: requireButtonElement(host, '#file-explorer-navigate-up', 'File Explorer #file-explorer-navigate-up'),
        rowsBody: requireTableSectionElement(host, '#file-explorer-rows-body', 'File Explorer #file-explorer-rows-body'),
        selectAllToggle: requireInputElement(host, '#file-explorer-select-all', 'File Explorer #file-explorer-select-all'),
        uploadFilesInput: requireInputElement(host, '#file-explorer-upload-files-input', 'File Explorer #file-explorer-upload-files-input'),
        uploadFolderInput: requireInputElement(host, '#file-explorer-upload-folder-input', 'File Explorer #file-explorer-upload-folder-input'),

        sortSelect: requireSelectElement(host, '#file-explorer-icon-sort', 'File Explorer #file-explorer-icon-sort'),
        sortShell: host.requireHTMLElement('.file-explorer-sort-shell'),
        newEntryShell: host.requireHTMLElement('.file-explorer-new-entry-shell'),
        viewModeToggleButton: requireButtonElement(host, '#file-explorer-view-mode-toggle', 'File Explorer #file-explorer-view-mode-toggle'),
        selectionSelectAllButton: requireButtonElement(host, '#file-explorer-selection-select-all', 'File Explorer #file-explorer-selection-select-all'),
        selectionDeselectAllButton: requireButtonElement(host, '#file-explorer-selection-deselect-all', 'File Explorer #file-explorer-selection-deselect-all'),
        selectionInverseButton: requireButtonElement(host, '#file-explorer-selection-inverse', 'File Explorer #file-explorer-selection-inverse'),
        toggleSelectionModeButton: requireButtonElement(host, '#file-explorer-toggle-selection-mode', 'File Explorer #file-explorer-toggle-selection-mode'),

        selectionMetadataButton: requireButtonElement(host, '#file-explorer-selection-metadata', 'File Explorer #file-explorer-selection-metadata'),
        selectionRenameButton: requireButtonElement(host, '#file-explorer-selection-rename', 'File Explorer #file-explorer-selection-rename'),
        selectionSoaiLinkButton: requireButtonElement(host, '#file-explorer-selection-soai-link', 'File Explorer #file-explorer-selection-soai-link'),
        selectionCopyButton: requireButtonElement(host, '#file-explorer-selection-copy', 'File Explorer #file-explorer-selection-copy'),
        selectionMoveButton: requireButtonElement(host, '#file-explorer-selection-move', 'File Explorer #file-explorer-selection-move'),
        selectionDeleteButton: requireButtonElement(host, '#file-explorer-selection-delete', 'File Explorer #file-explorer-selection-delete'),
        selectionDownloadButton: requireButtonElement(host, '#file-explorer-selection-download', 'File Explorer #file-explorer-selection-download'),
        copyHereButton: requireButtonElement(host, '#file-explorer-copy-here', 'File Explorer #file-explorer-copy-here'),
        moveHereButton: requireButtonElement(host, '#file-explorer-move-here', 'File Explorer #file-explorer-move-here'),
        transferCancelButton: requireButtonElement(host, '#file-explorer-transfer-cancel', 'File Explorer #file-explorer-transfer-cancel'),

        taskPanel: host.requireHTMLElement('#file-explorer-task-panel'),
        taskToggleButton: requireButtonElement(host, '#file-explorer-task-toggle', 'File Explorer #file-explorer-task-toggle'),
        taskCount: host.requireHTMLElement('#file-explorer-task-count'),
        taskLabel: host.requireHTMLElement('#file-explorer-task-label'),
        taskDetails: host.requireHTMLElement('#file-explorer-task-details'),
        taskSummaryBar: host.requireHTMLElement('#file-explorer-task-progress-summary'),
        taskSummaryBarFill: host.requireHTMLElement('#file-explorer-task-progress-fill'),
        taskSummaryValue: host.requireHTMLElement('#file-explorer-task-progress-value'),
        taskId: host.requireHTMLElement('#file-explorer-task-id'),
        taskProgress: host.requireHTMLElement('#file-explorer-task-progress')
    };
};

const optionalFileExplorerRoot = (host: FileExplorerDomHost): HTMLElement | null => host.optionalHTMLElement('#file-explorer-root');

export { optionalFileExplorerRoot, requireFileExplorerRoot, requireFileExplorerUi };
