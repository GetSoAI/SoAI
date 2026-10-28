/* SoAI - File Explorer bounded table rows widget [frontend/assets/ts/pages/fileexplorer/rendering/FileExplorerRowsWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { BoundedCollectionRenderer, createEdgeLoader } from '@core/data/boundedcollectionrenderer/public.ts';
import { createHtmlTableRow } from '@core/dom/html.ts';
import { parentVirtualPath } from '@core/fileexplorerbrowser/paths.ts';
import type { FileBrowserEntry } from '@core/fileexplorerbrowser/types.ts';
import { i18n } from '@core/i18n/index.ts';
import { TimeoutTimer } from '@core/timers/timeoutTimer.ts';
import { createDeferred, type Deferred } from '@core/runtime/deferred.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { renderFileExplorerEntryRowMarkup, renderFileExplorerLoadingRowMarkup, renderFileExplorerMessageRowMarkup, renderFileExplorerParentRowMarkup } from '@pages/fileexplorer/rendering/FileExplorerTableRowsWidget.ts';

type FileExplorerRenderedRow = { id: string; variant: 'empty' } | { id: string; variant: 'error'; message: string } | { id: string; variant: 'entry'; entry: FileBrowserEntry } | { id: string; variant: 'loading'; label: string } | { id: string; variant: 'parent'; path: string };

interface FileExplorerRowsWidgetOptions {
    rowsBody: HTMLTableSectionElement;
    getIconSync: (iconName: IconName, options?: IconOptions) => TrustedHtml;
    isRecentEntry: (entry: FileBrowserEntry) => boolean;
    revealRows: () => void;
    armCommittedRows: (rows: readonly HTMLElement[]) => void;
    onCommit: () => void;
    onError: (error: Error) => void;
}

interface FileExplorerRowsUpdate {
    entries: readonly FileBrowserEntry[];
    currentPath: string;
    isLoading: boolean;
    sessionRevision?: number;
    isLoadingMore: boolean;
    loadingLabel: string;
    resetScroll: boolean;
    animateLayout?: boolean | undefined;
    errorMessage?: string | null | undefined;
}

const EMPTY_ROW_ID = 'file-explorer:empty';
const ERROR_ROW_ID = 'file-explorer:error';
const LOADING_ROW_ID = 'file-explorer:loading';
const PARENT_ROW_ID = 'file-explorer:parent';
const LOADING_ROW_DELAY_MS = 250;
const entryRowId = (path: string): string => `file-explorer:entry:${path}`;

class FileExplorerRowsWidget {
    readonly #rowsBody: HTMLTableSectionElement;
    readonly #getIconSync: (iconName: IconName, options?: IconOptions) => TrustedHtml;
    readonly #isRecentEntry: (entry: FileBrowserEntry) => boolean;
    readonly #renderer: BoundedCollectionRenderer<FileExplorerRenderedRow>;
    #isLoading = false;
    #isLoadingMore = false;
    #loadingLabel = i18n.t('fileExplorer.status.loading');
    #loadedEndRendered = false;
    #loadedEndWaiter: Deferred<boolean> | null = null;
    #networkLoader: HTMLElement | null = null;
    #loadingRowTimer: TimeoutTimer | null = null;
    #showLoadingRow = false;
    #loadingSessionRevision: number | null = null;
    #latestUpdate: FileExplorerRowsUpdate | null = null;
    #renderedPath: string | null = null;
    #revealOnCommit = false;
    #rowIds: readonly string[] = [];
    #rowSignatures: ReadonlyMap<string, string> = new Map();

    constructor(options: FileExplorerRowsWidgetOptions) {
        this.#rowsBody = options.rowsBody;
        this.#getIconSync = options.getIconSync;
        this.#isRecentEntry = options.isRecentEntry;
        this.#renderer = new BoundedCollectionRenderer<FileExplorerRenderedRow>({
            resolveContainer: () => this.#rowsBody,
            renderItem: (row) => this.#renderRow(row),
            resolveItemIdentifier: (element) => element.dataset['fileExplorerRowId'] ?? null,
            loadingLabel: () => this.#loadingLabel,
            onCommit: (context) => {
                if (!this.#isLoadingMore) {
                    this.#loadedEndRendered = !this.#isLoading && context.rangeEnd === context.totalCount;
                }
                if (this.#loadedEndRendered) this.#settleLoadedEndWaiter(true);
                this.#syncNetworkLoader();
                if (!this.#isLoading) {
                    if (this.#revealOnCommit) {
                        this.#revealOnCommit = false;
                        options.revealRows();
                    } else {
                        options.armCommittedRows(context.enteringElements);
                    }
                }
                options.onCommit();
            },
            onError: (error) => {
                this.#settleLoadedEndWaiter(false);
                options.onError(error);
            }
        });
    }

    update(input: FileExplorerRowsUpdate): void {
        this.#latestUpdate = input;
        if (input.isLoading) this.#settleLoadedEndWaiter(false);
        if (input.isLoading) {
            if (input.sessionRevision !== undefined && this.#loadingSessionRevision !== input.sessionRevision) {
                this.#cancelLoadingRow();
                this.#loadingSessionRevision = input.sessionRevision;
            }
            this.#scheduleLoadingRow();
        } else {
            this.#cancelLoadingRow();
            this.#loadingSessionRevision = null;
        }
        if (this.#renderedPath !== input.currentPath) {
            this.#renderedPath = input.currentPath;
            this.#revealOnCommit = true;
        }
        const rows = this.#buildRows(input);
        const rowIds = rows.map((row) => row.id);
        const rowSignatures = new Map(rows.map((row) => [row.id, this.#rowSignature(row)]));
        const dirtyIds = rowIds.filter((identifier) => {
            const previous = this.#rowSignatures.get(identifier);
            return previous !== undefined && previous !== rowSignatures.get(identifier);
        });
        const sequenceChanged = rowIds.length !== this.#rowIds.length || rowIds.some((identifier, index) => identifier !== this.#rowIds[index]);
        this.#isLoading = input.isLoading;
        this.#isLoadingMore = input.isLoadingMore;
        this.#loadingLabel = input.loadingLabel;
        if (sequenceChanged) this.#loadedEndRendered = false;
        this.#rowIds = rowIds;
        this.#rowSignatures = rowSignatures;
        if (!input.isLoadingMore) this.#removeNetworkLoader();
        this.#renderer.update({
            ids: rowIds,
            lookup: new Map(rows.map((row) => [row.id, row])),
            dirtyIds,
            resetScroll: input.resetScroll,
            animateLayout: input.animateLayout === true
        });
        this.#syncNetworkLoader();
    }

    isLoadedEndRendered(): boolean {
        return !this.#isLoadingMore && this.#loadedEndRendered;
    }

    async waitForLoadedEnd(): Promise<boolean> {
        if (this.isLoadedEndRendered()) return true;
        this.#loadedEndWaiter ??= createDeferred<boolean>();
        return await this.#loadedEndWaiter.promise;
    }

    prepareForViewModeChange(): void {
        this.#revealOnCommit = true;
        this.#renderer.prepareForViewModeChange();
    }

    async revealPath(path: string): Promise<boolean> {
        return await this.#renderer.reveal(entryRowId(path));
    }

    dispose(): void {
        this.#cancelLoadingRow();
        this.#settleLoadedEndWaiter(false);
        this.#removeNetworkLoader();
        this.#renderer.dispose();
        this.#rowIds = [];
        this.#rowSignatures = new Map();
        this.#latestUpdate = null;
        this.#loadingSessionRevision = null;
        this.#renderedPath = null;
        this.#revealOnCommit = false;
    }

    #buildRows(input: FileExplorerRowsUpdate): FileExplorerRenderedRow[] {
        if (input.isLoading) return this.#showLoadingRow ? [{ id: LOADING_ROW_ID, variant: 'loading', label: input.loadingLabel }] : [];
        const rows: FileExplorerRenderedRow[] = [];
        if (input.currentPath !== '/') {
            rows.push({
                id: PARENT_ROW_ID,
                variant: 'parent',
                path: parentVirtualPath(input.currentPath)
            });
        }
        for (const entry of input.entries) {
            rows.push({ id: entryRowId(entry.path), variant: 'entry', entry });
        }
        if (input.entries.length === 0 && input.errorMessage) {
            rows.push({ id: ERROR_ROW_ID, variant: 'error', message: input.errorMessage });
        } else if (input.entries.length === 0 && input.currentPath === '/') {
            rows.push({ id: EMPTY_ROW_ID, variant: 'empty' });
        }
        return rows;
    }

    #scheduleLoadingRow(): void {
        if (this.#showLoadingRow || this.#loadingRowTimer !== null) return;
        this.#loadingRowTimer = new TimeoutTimer(LOADING_ROW_DELAY_MS, () => {
            this.#loadingRowTimer = null;
            if (!this.#latestUpdate?.isLoading) return;
            this.#showLoadingRow = true;
            this.update(this.#latestUpdate);
        });
        this.#loadingRowTimer.start();
    }

    #cancelLoadingRow(): void {
        if (this.#loadingRowTimer !== null) {
            this.#loadingRowTimer.stop();
            this.#loadingRowTimer = null;
        }
        this.#showLoadingRow = false;
    }

    #renderRow(row: FileExplorerRenderedRow): HTMLTableRowElement {
        let markup: TrustedHtml;
        if (row.variant === 'entry') {
            markup = renderFileExplorerEntryRowMarkup(row.entry, this.#getIconSync, this.#isRecentEntry);
        } else if (row.variant === 'parent') {
            markup = renderFileExplorerParentRowMarkup(row.path, this.#getIconSync);
        } else if (row.variant === 'loading') {
            markup = renderFileExplorerLoadingRowMarkup(row.label);
        } else if (row.variant === 'error') {
            markup = renderFileExplorerMessageRowMarkup(row.message, 'error');
        } else {
            markup = renderFileExplorerMessageRowMarkup(i18n.t('fileExplorer.status.empty'), 'empty');
        }
        const element = createHtmlTableRow({
            documentRef: this.#rowsBody.ownerDocument,
            html: markup,
            context: this.#rowsBody
        });
        element.dataset['fileExplorerRowId'] = row.id;
        return element;
    }

    #syncNetworkLoader(): void {
        if (!this.#isLoadingMore) return;
        if (this.#networkLoader === null) {
            this.#networkLoader = createEdgeLoader(this.#rowsBody, 'forward', this.#loadingLabel);
        }
        if (this.#networkLoader.parentElement !== this.#rowsBody) {
            this.#rowsBody.append(this.#networkLoader);
        }
    }

    #removeNetworkLoader(): void {
        this.#networkLoader?.remove();
        this.#networkLoader = null;
    }

    #settleLoadedEndWaiter(loadedEndReached: boolean): void {
        this.#loadedEndWaiter?.resolve(loadedEndReached);
        this.#loadedEndWaiter = null;
    }

    #rowSignature(row: FileExplorerRenderedRow): string {
        if (row.variant === 'entry') {
            const entry = row.entry;
            return JSON.stringify([entry.name, entry.isDirectory, entry.size, entry.modifiedAt, entry.modifiedAtTimestamp, entry.mimeType, entry.permissions, this.#isRecentEntry(entry)]);
        }
        if (row.variant === 'parent') return row.path;
        if (row.variant === 'error') return `${row.variant}:${row.message}`;
        return row.variant === 'loading' ? `${row.variant}:${row.label}` : row.variant;
    }
}

export { FileExplorerRowsWidget };
export type { FileExplorerRowsUpdate, FileExplorerRowsWidgetOptions };
