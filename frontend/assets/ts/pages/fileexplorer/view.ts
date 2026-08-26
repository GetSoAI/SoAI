/* SoAI - File explorer page rendering [frontend/assets/ts/pages/fileexplorer/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderLabelAttributes, toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { FILE_EXPLORER_ACTION_SELECT_ALL, FILE_EXPLORER_ACTION_SORT, FILE_EXPLORER_ACTION_TASK_PANEL_TOGGLE, FILE_EXPLORER_ACTION_UPLOAD_FILES } from '@features/fileexplorer/public.ts';
import { renderFileExplorerHeaderWidget, type FileExplorerHeaderWidgetDependencies } from '@pages/fileexplorer/rendering/FileExplorerHeaderWidget.ts';
import { renderFileExplorerStatusBar } from '@pages/fileexplorer/rendering/FileExplorerStatusBarWidget.ts';
import { renderFileExplorerLoadingRowMarkup } from '@pages/fileexplorer/rendering/FileExplorerTableRowsWidget.ts';

const CONTENT_SLOT_MARKER = '<!-- Page content goes here -->';

const renderSortableHeader = (dependencies: FileExplorerHeaderWidgetDependencies, column: 'name' | 'type' | 'size' | 'modified', label: string): string => {
    const active = dependencies.sortState.column === column;
    const direction = active ? (dependencies.sortState.direction === 'asc' ? 'ascending' : 'descending') : 'none';
    return `<th class="sortable${active ? ' is-active' : ''}" data-action="${FILE_EXPLORER_ACTION_SORT}" data-sort="${column}" tabindex="0" role="columnheader" aria-sort="${direction}" ${renderLabelAttributes(label)}>${label} <span class="sort-indicator"></span></th>`;
};

const renderFileExplorerPageView = (dependencies: FileExplorerHeaderWidgetDependencies): TrustedHtml => {
    const { header, initialViewMode } = renderFileExplorerHeaderWidget(dependencies);

    const content = `
	        <section id="file-explorer-root" class="file-explorer-layout" data-view-mode="${initialViewMode}">
	            <section class="file-explorer-card file-explorer-table-wrap">
	                <table class="file-explorer-table">
	                    <colgroup>
	                        <col class="file-explorer-table-col file-explorer-table-col--select">
	                        <col class="file-explorer-table-col file-explorer-table-col--data">
	                        <col class="file-explorer-table-col file-explorer-table-col--data">
	                        <col class="file-explorer-table-col file-explorer-table-col--data">
	                        <col class="file-explorer-table-col file-explorer-table-col--data">
	                    </colgroup>
	                    <thead>
	                        <tr>
			                            <th class="file-explorer-table-select-col">
			                                <input id="file-explorer-select-all" type="checkbox" data-action="${FILE_EXPLORER_ACTION_SELECT_ALL}" aria-label="${i18n.t('fileExplorer.aria.selectAll')}">
			                            </th>
		                            ${renderSortableHeader(dependencies, 'name', i18n.t('fileExplorer.table.name'))}
		                            ${renderSortableHeader(dependencies, 'type', i18n.t('fileExplorer.table.type'))}
		                            ${renderSortableHeader(dependencies, 'size', i18n.t('fileExplorer.table.size'))}
		                            ${renderSortableHeader(dependencies, 'modified', i18n.t('fileExplorer.table.modified'))}
		                        </tr>
		                    </thead>
		                    <tbody id="file-explorer-rows-body" class="file-explorer-rows-body">
		                        ${renderFileExplorerLoadingRowMarkup(i18n.t('fileExplorer.status.loading')).html}
		                    </tbody>
		                </table>

	                    ${renderFileExplorerStatusBar().html}

	                    <input id="file-explorer-upload-files-input" class="u-hidden" type="file" data-action="${FILE_EXPLORER_ACTION_UPLOAD_FILES}" multiple>
	                    <input id="file-explorer-upload-folder-input" class="u-hidden" type="file" data-action="${FILE_EXPLORER_ACTION_UPLOAD_FILES}" multiple directory webkitdirectory>
		            </section>

	            <section id="file-explorer-task-panel" class="file-explorer-card file-explorer-task-panel u-hidden is-collapsed">
                    <button id="file-explorer-task-toggle" type="button" class="file-explorer-task-summary"
                        data-action="${FILE_EXPLORER_ACTION_TASK_PANEL_TOGGLE}" aria-expanded="false" aria-controls="file-explorer-task-details" ${renderLabelAttributes(i18n.t('fileExplorer.labels.tasks'))}>
                        <div class="file-explorer-task-summary-head">
                            <div class="file-explorer-task-summary-copy">
	                            <div class="file-explorer-task-line"><span class="file-explorer-label">${i18n.t('fileExplorer.labels.tasks')}</span><span id="file-explorer-task-count">0</span></div>
	                            <div class="file-explorer-task-line"><span class="file-explorer-label">${i18n.t('fileExplorer.labels.latestTask')}</span><span id="file-explorer-task-label">${i18n.t('fileExplorer.labels.none')}</span></div>
                            </div>
                            <span class="file-explorer-task-toggle-indicator" aria-hidden="true"></span>
                        </div>
                        <div class="file-explorer-task-summary-progress-row">
                            <div id="file-explorer-task-progress-summary" class="file-explorer-task-summary-progress progress-bar"
                                role="progressbar" aria-label="${i18n.t('fileExplorer.labels.tasks')}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">
                                <span id="file-explorer-task-progress-fill" class="file-explorer-task-summary-progress-fill progress-fill"></span>
                            </div>
                            <span id="file-explorer-task-progress-value" class="file-explorer-task-progress-value">0%</span>
                        </div>
                    </button>
                    <div id="file-explorer-task-details" class="file-explorer-task-details">
	                    <div class="file-explorer-task-line"><span class="file-explorer-label">${i18n.t('fileExplorer.labels.task_id')}</span><code id="file-explorer-task-id" class="file-explorer-task-id">-</code></div>
                        <div id="file-explorer-task-progress" class="file-explorer-task-progress"></div>
                    </div>
		            </section>
	        </section>

	    `;

    if (!header.html.includes(CONTENT_SLOT_MARKER)) {
        throw new Error('File Explorer standard header is missing the content slot marker');
    }
    return toTrustedUiHtml(header.html.replace(CONTENT_SLOT_MARKER, content));
};

export { renderFileExplorerPageView };
