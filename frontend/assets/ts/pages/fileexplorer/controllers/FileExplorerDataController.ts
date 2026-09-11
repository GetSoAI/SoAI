/* SoAI - File explorer page control layer data controller [frontend/assets/ts/pages/fileexplorer/controllers/FileExplorerDataController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { buildSignalRequestOptions } from '@core/api/requestOptions.ts';
import { FILE_EXPLORER_SORT_COLUMN_DEFAULT_DIRECTIONS, FILE_EXPLORER_SORT_COLUMNS, sortFileExplorerEntries, type FileExplorerSortColumn } from '@core/fileexplorerbrowser/entrySorting.ts';
import { DirectoryListingController } from '@core/fileexplorerbrowser/directoryListingController.ts';
import { isFileBrowserImagePreviewMimeType } from '@core/fileexplorerbrowser/mediaClassification.ts';
import { parseFileBrowserMetadataPayload, parseFileBrowserReadPayload } from '@core/fileexplorerbrowser/payloads.ts';
import { basenameVirtualPath, parentVirtualPath, resolveAbsolutePath, resolveFileBrowserEnteredPath, toVirtualPath } from '@core/fileexplorerbrowser/paths.ts';
import type { DirectoryListingBrowserState, FileBrowserEntry, FileBrowserMetadata } from '@core/fileexplorerbrowser/types.ts';
import { i18n } from '@core/i18n/index.ts';
import { requireSortableColumn, requireSortableHeaders, resolveNextSortState, updateSortableTableIndicators, type SortDirection } from '@core/ui/tables/sortableTable.ts';
import { syncSortControl } from '@core/uiprimitives/sortableList.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { notifyFileExplorerHttpError, resolveFileExplorerBrowserErrorMessage } from '@pages/fileexplorer/controllers/fileExplorerHttpErrorController.ts';
import type { FileExplorerRecentUploadController } from '@pages/fileexplorer/controllers/FileExplorerRecentUploadController.ts';
import { FileExplorerUploadRevealController } from '@pages/fileexplorer/controllers/FileExplorerUploadRevealController.ts';
import type { FileExplorerRowsRevealController } from '@pages/fileexplorer/controllers/fileExplorerRowsRevealController.ts';
import { createFileExplorerSortControlDefinition, type FileExplorerSortState } from '@pages/fileexplorer/controllers/page/fileExplorerPageControlsController.ts';
import type { FileExplorerSelectionModel } from '@pages/fileexplorer/state/FileExplorerSelectionState.ts';
import { FileExplorerBreadcrumbWidget } from '@pages/fileexplorer/rendering/FileExplorerBreadcrumbWidget.ts';
import { FileExplorerRowsWidget } from '@pages/fileexplorer/rendering/FileExplorerRowsWidget.ts';
import { syncRowSelectionControls } from '@pages/fileexplorer/rendering/FileExplorerTableRowsWidget.ts';
import type { FileExplorerControllerHost, FileExplorerUiRefs } from '@pages/fileexplorer/types.ts';

class FileExplorerDataController {
    readonly #host: FileExplorerControllerHost;
    readonly #ui: FileExplorerUiRefs;
    readonly #onStateChanged: (currentPath: string, isLoading: boolean) => void;
    readonly #browser: DirectoryListingController;
    readonly #recentUploads: FileExplorerRecentUploadController;
    readonly #selection: FileExplorerSelectionModel;
    readonly #persistSort: (state: FileExplorerSortState) => void;
    readonly #uploadReveal: FileExplorerUploadRevealController;
    readonly #rowsRenderer: FileExplorerRowsWidget;
    readonly #breadcrumb: FileExplorerBreadcrumbWidget;
    #currentPath = '/';
    #displayPath = '/';
    #workspacePathResolved: string | null = null;
    #entries: FileBrowserEntry[] = [];
    #sortColumn: FileExplorerSortColumn = 'name';
    #sortDirection: SortDirection = 'asc';
    #isLoading = false;
    #isLoadingMore = false;
    #query = '';
    #preservedScrollTop: number | null = null;
    #resetRowsScroll = false;

    constructor(dependencies: { host: FileExplorerControllerHost; ui: FileExplorerUiRefs; initialSort: FileExplorerSortState; persistSort: (state: FileExplorerSortState) => void; recentUploads: FileExplorerRecentUploadController; selection: FileExplorerSelectionModel; rowsReveal: FileExplorerRowsRevealController; onStateChanged: (currentPath: string, isLoading: boolean) => void; onRowsCommitted?: (() => void) | undefined }) {
        this.#host = dependencies.host;
        this.#ui = dependencies.ui;
        this.#sortColumn = dependencies.initialSort.column;
        this.#sortDirection = dependencies.initialSort.direction;
        this.#persistSort = dependencies.persistSort;
        this.#recentUploads = dependencies.recentUploads;
        this.#selection = dependencies.selection;
        this.#onStateChanged = dependencies.onStateChanged;
        this.#uploadReveal = new FileExplorerUploadRevealController({
            rowsBody: dependencies.ui.rowsBody,
            recentUploads: dependencies.recentUploads
        });
        this.#browser = new DirectoryListingController({
            api: dependencies.host.api,
            awaitTask: dependencies.host.awaitTask,
            errorResolver: { resolve: (error) => resolveFileExplorerBrowserErrorMessage(error) },
            initialSort: { column: this.#sortColumn, direction: this.#sortDirection },
            onError: (error) => this.#handleError(error, 'File Explorer data operation failed'),
            onStateChange: (state) => this.#applyBrowserState(state)
        });
        this.#rowsRenderer = new FileExplorerRowsWidget({
            rowsBody: dependencies.ui.rowsBody,
            getIconSync: dependencies.host.getIconSync,
            isRecentEntry: (entry) => dependencies.recentUploads.isEntryRecent(entry),
            revealRows: () => dependencies.rowsReveal.reveal(),
            armCommittedRows: (rows) => dependencies.rowsReveal.armCommittedRows(rows),
            onCommit: () => this.#handleRowsCommit(dependencies.onRowsCommitted),
            onError: (error) => this.#handleError(error, 'File Explorer row rendering failed')
        });
        this.#breadcrumb = new FileExplorerBreadcrumbWidget({ container: dependencies.ui.breadcrumb, getIconSync: (name, options) => dependencies.host.getIconSync(name, options) });
        this.#syncSortSelect();
    }

    destroy(): void {
        this.#browser.destroy();
        this.#rowsRenderer.dispose();
        this.#breadcrumb.dispose();
    }

    getCurrentPath(): string {
        return this.#currentPath;
    }

    getDisplayPath(): string {
        return this.#displayPath;
    }

    resolveEnteredPath(value: string): string | null {
        return resolveFileBrowserEnteredPath(this.#workspacePathResolved, value);
    }

    getCurrentFolderImagePaths(): readonly string[] {
        return sortFileExplorerEntries(this.#entries, this.#sortColumn, this.#sortDirection)
            .filter((entry) => {
                return !entry.isDirectory && parentVirtualPath(entry.path) === this.#currentPath && isFileBrowserImagePreviewMimeType(entry.mimeType);
            })
            .map((entry) => entry.path);
    }

    async initialize(path: string = '/'): Promise<void> {
        await this.#browser.initialize(path);
    }

    async refreshList(): Promise<void> {
        await this.#browser.refresh();
    }

    async navigate(path: string): Promise<void> {
        await this.#browser.navigate(path);
    }

    async search(query: string): Promise<void> {
        await this.#browser.search(query);
    }

    async clearSearch(): Promise<void> {
        await this.#browser.clearSearch();
    }

    async loadNextPage(): Promise<void> {
        if (!(await this.#rowsRenderer.waitForLoadedEnd())) return;
        await this.#browser.loadNextPage();
    }

    prepareForViewModeChange(): void {
        this.#rowsRenderer.prepareForViewModeChange();
    }

    reapplyAfterViewModeChange(): void {
        this.#renderRows();
    }

    async revealPath(path: string): Promise<boolean> {
        const normalizedPath = toVirtualPath(path);
        if (parentVirtualPath(normalizedPath) !== this.#currentPath) return false;
        const found = await this.#browser.loadPageContaining(basenameVirtualPath(normalizedPath));
        return found && (await this.#rowsRenderer.revealPath(normalizedPath));
    }

    async loadMetadata(path: string, signal?: AbortSignal): Promise<FileBrowserMetadata> {
        return parseFileBrowserMetadataPayload(await this.#host.api.metadata(toVirtualPath(path), buildSignalRequestOptions({ signal })));
    }

    async readPath(path: string): Promise<{ path: string; content: string }> {
        const parsed = parseFileBrowserReadPayload(await this.#host.api.read(toVirtualPath(path)));
        return { path: parsed.path, content: parsed.content };
    }

    syncSelectionRows(): void {
        const selectedPaths = new Set(this.#selection.getSelectedPaths());
        syncRowSelectionControls(this.#ui.rowsBody, selectedPaths);
        const selectionCount = selectedPaths.size;
        const entryCount = this.#entries.length;
        const selectedEntryCount = this.#entries.filter((entry) => selectedPaths.has(entry.path)).length;
        this.#ui.selectionCount.textContent = String(selectionCount);
        this.#ui.selectAllToggle.checked = entryCount > 0 && selectedEntryCount === entryCount;
        this.#ui.selectAllToggle.indeterminate = selectedEntryCount > 0 && selectedEntryCount < entryCount;
    }

    async sort(column: string): Promise<void> {
        const sortColumn = requireSortableColumn(FILE_EXPLORER_SORT_COLUMNS, column, 'file explorer');
        const nextSort = resolveNextSortState({ column: this.#sortColumn, direction: this.#sortDirection }, sortColumn, FILE_EXPLORER_SORT_COLUMN_DEFAULT_DIRECTIONS[sortColumn]);
        this.#sortColumn = nextSort.column;
        this.#sortDirection = nextSort.direction;
        this.#persistSortState();
        await this.#renderAfterSortChange();
    }

    #persistSortState(): void {
        this.#persistSort({ column: this.#sortColumn, direction: this.#sortDirection });
    }

    async #renderAfterSortChange(): Promise<void> {
        if (!this.#query) {
            await this.#browser.setSort(this.#sortColumn, this.#sortDirection);
            return;
        }
        if (this.#isLoading) {
            this.#renderRows();
            return;
        }
        this.#renderRows();
        this.#emitStateChanged();
    }

    #applyBrowserState(state: DirectoryListingBrowserState): void {
        if (state.isLoading) {
            const samePath = toVirtualPath(state.currentPath) === toVirtualPath(this.#currentPath);
            this.#preservedScrollTop = samePath ? this.#ui.rowsBody.scrollTop : null;
            this.#resetRowsScroll = !samePath;
            this.#recentUploads.handleListingLoad(state.currentPath, state.sessionRevision);
        }
        this.#currentPath = state.currentPath;
        this.#workspacePathResolved = state.workspacePathResolved;
        this.#query = state.query;
        this.#isLoading = state.isLoading;
        this.#isLoadingMore = state.isLoadingMore;
        this.#entries = state.isLoading ? [] : [...state.entries];
        if (state.isLoading) {
            this.#renderRows();
            this.#renderBreadcrumb(state.currentPath);
            this.#ui.resultCount.textContent = i18n.t('common.loading');
            setTooltipText(this.#ui.resultCount, this.#loadingLabel());
            this.#updateSortIndicators();
            this.#selection.beginLoading(state.currentPath);
            this.#emitStateChanged();
            return;
        }
        this.#renderRows();
        this.#renderBreadcrumb(state.currentPath);
        const truncatedSearch = Boolean(state.query) && state.truncated;
        this.#ui.resultCount.textContent = truncatedSearch ? `${this.#entries.length}+` : String(state.total);
        setTooltipText(this.#ui.resultCount, truncatedSearch ? i18n.t('fileExplorer.labels.resultsTruncated') : '');
        this.#selection.syncEntries(
            state.currentPath,
            this.#entries.map((entry) => entry.path)
        );
        this.#emitStateChanged();
    }

    #renderBreadcrumb(currentPath: string): void {
        this.#displayPath = resolveAbsolutePath(this.#workspacePathResolved, currentPath) ?? currentPath;
        this.#breadcrumb.render({
            virtualPath: currentPath,
            displayPath: this.#displayPath,
            workspaceRootLabel: resolveAbsolutePath(this.#workspacePathResolved, '/') ?? '/'
        });
    }

    #renderRows(): void {
        const sorted = this.#query ? sortFileExplorerEntries(this.#entries, this.#sortColumn, this.#sortDirection) : this.#entries;
        this.#rowsRenderer.update({
            entries: this.#isLoading ? [] : sorted,
            currentPath: this.#currentPath,
            isLoading: this.#isLoading,
            isLoadingMore: this.#isLoadingMore,
            loadingLabel: this.#loadingLabel(),
            resetScroll: this.#resetRowsScroll
        });
        this.#updateSortIndicators();
    }

    #loadingLabel(): string {
        return this.#query ? i18n.t('fileExplorer.status.searching') : i18n.t('fileExplorer.status.loading');
    }

    #handleRowsCommit(onRowsCommitted: (() => void) | undefined): void {
        if (!this.#isLoading && this.#preservedScrollTop !== null) {
            this.#ui.rowsBody.scrollTop = this.#preservedScrollTop;
            this.#preservedScrollTop = null;
        }
        if (!this.#isLoading) this.#resetRowsScroll = false;
        const mountedPaths = new Set(
            Array.from(this.#ui.rowsBody.rows)
                .map((row) => row.dataset['path'])
                .filter((path): path is string => path !== undefined)
        );
        this.#uploadReveal.reveal(this.#entries.filter((entry) => mountedPaths.has(entry.path)));
        this.syncSelectionRows();
        onRowsCommitted?.();
    }

    #updateSortIndicators(): void {
        const table = this.#ui.rowsBody.closest('table');
        if (!table) {
            throw new Error('File Explorer table is missing required sortable header scope');
        }
        updateSortableTableIndicators({
            headers: requireSortableHeaders(table, 'File Explorer'),
            activeColumn: this.#sortColumn,
            activeDirection: this.#sortDirection,
            host: this.#host
        });
        this.#syncSortSelect();
    }

    #syncSortSelect(): void {
        syncSortControl(this.#ui.sortSelect, createFileExplorerSortControlDefinition({ column: this.#sortColumn, direction: this.#sortDirection }));
    }

    #emitStateChanged(): void {
        this.#onStateChanged(this.#currentPath, this.#isLoading);
    }

    #handleError(error: Error, context: string): void {
        if (notifyFileExplorerHttpError(this.#host, error)) {
            return;
        }
        this.#host.handleError(error, context, { notify: true });
    }
}

export { FileExplorerDataController };
