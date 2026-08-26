/* SoAI - File explorer page route implementation [frontend/assets/ts/pages/fileexplorer/FileExplorerPage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BasePageDependencies } from '@core/routing/pages/pagetypes/public.ts';
import { shouldPreventDefaultForActionElement } from '@core/dom/dataAction.ts';
import { bindPageActionDispatcher } from '@core/dom/dataActionBinding.ts';
import { dom } from '@core/dom/dom.ts';
import { signalAborted } from '@core/lifecycle/abortSignals.ts';
import { i18n } from '@core/i18n/index.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { StaticBasePage, type RenderContext } from '@core/StaticBasePage.ts';
import { isObject, isString } from '@core/typeGuards.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { CONTENT_PREVIEW_MODAL_ID } from '@core/ui/modals/contentpreview/constants.ts';
import { parentVirtualPath, toVirtualPath } from '@core/fileexplorerbrowser/paths.ts';
import { normalizeSearchDisplayQuery } from '@core/search/searchQuery.ts';
import { measureScrollEdges } from '@core/dom/scrollGeometry.ts';
import { InlineTextEditController } from '@core/ui/inlineedit/controller.ts';
import { FILE_EXPLORER_METADATA_MODAL_ID } from '@features/fileexplorer/public.ts';
import { FILE_EXPLORER_ACTION_CLEAR_HIGHLIGHT, FILE_EXPLORER_ACTION_NAVIGATE_HOME, FILE_EXPLORER_ACTION_NAVIGATE_NEXT, FILE_EXPLORER_ACTION_NAVIGATE_PATH, FILE_EXPLORER_ACTION_NAVIGATE_PREVIOUS, FILE_EXPLORER_ACTION_NAVIGATE_UP, FILE_EXPLORER_ACTION_PATH_EDIT_SAVE, FILE_EXPLORER_ACTION_PATH_EDIT_START, isFileExplorerChangeActionId, isFileExplorerClickActionId, isFileexplorerActionId } from '@pages/fileexplorer/actions.ts';
import { createFileExplorerPageRuntime } from '@pages/fileexplorer/controllers/page/runtime.ts';
import { awaitDirectoryListingTask } from '@pages/fileexplorer/controllers/page/DirectoryListingTaskSession.ts';
import { renderFileExplorerPageView } from '@pages/fileexplorer/view.ts';
import { hydrateFileExplorerSortState, type FileExplorerSortState } from '@pages/fileexplorer/controllers/page/fileExplorerPageControlsController.ts';

export const PAGE_ID = 'fileExplorer';
export const PAGE_MODULE_ID = 'pages.FileExplorerPage';

class FileExplorerPage extends StaticBasePage {
    #runtime: ReturnType<typeof createFileExplorerPageRuntime> | null = null;
    #pathEditController: InlineTextEditController | null = null;
    #initialSortState: FileExplorerSortState | null = null;

    constructor(basePageDependencies: BasePageDependencies) {
        super(PAGE_ID, { dependencies: basePageDependencies });
        this.layout.configure({ collapseActionsMenuToFit: true });
    }

    override getRequiredResources(): string[] {
        return [];
    }

    override async beforeRender(parameters: JsonObject): Promise<JsonObject> {
        await super.beforeRender(parameters);
        return {};
    }

    override async renderView(_context: RenderContext): Promise<TrustedHtml> {
        this.#initialSortState = hydrateFileExplorerSortState(this.dependencies.storage);
        return renderFileExplorerPageView({
            getIconSync: (name, options) => this.services.getIconSync(name, options),
            generateStandardHeader: (options) => this.layout.generateHeader(options),
            sortState: this.#initialSortState
        });
    }

    override async setupPage(parameters: JsonObject | null = null, context: { signal?: AbortSignal } = {}): Promise<void> {
        if (this.#runtime) {
            return;
        }
        const parameterRecord = isObject(parameters) ? parameters : {};
        const pathParameter = isString(parameterRecord['path']) && parameterRecord['path'].trim() ? toVirtualPath(parameterRecord['path']) : null;
        const highlightParameter = isString(parameterRecord['highlight']) && parameterRecord['highlight'].trim() ? toVirtualPath(parameterRecord['highlight']) : null;
        const previewParameter = isString(parameterRecord['preview']) && parameterRecord['preview'].trim() ? toVirtualPath(parameterRecord['preview']) : null;
        const searchParameter = normalizeSearchDisplayQuery(parameterRecord['search'] ?? null) || null;
        const initialPath = pathParameter ? pathParameter : highlightParameter ? parentVirtualPath(highlightParameter) : '/';
        if (!this.#initialSortState) throw new Error('File Explorer sort state must be hydrated before runtime setup');

        const modalPresenter = requireModalPresenter();
        this.#runtime = createFileExplorerPageRuntime(
            {
                api: this.dependencies.api,
                storage: this.dependencies.storage,
                pageLifecycle: this.pageLifecycle,
                pageDom: this.pageDom,
                feedback: this.feedback,
                services: this.services,
                layout: this.layout,
                modalPresenter,
                waitForTask: async (taskId, signal) => {
                    const streamRuntime = await this.streaming.ensureRuntime();
                    await awaitDirectoryListingTask((acceptedTaskId) => streamRuntime.tasks.trackAcceptedTask(acceptedTaskId), taskId, signal);
                }
            },
            {
                initialPath,
                highlightPath: highlightParameter,
                searchQuery: searchParameter,
                previewPath: previewParameter,
                sortState: this.#initialSortState
            }
        );
        if (signalAborted(context.signal ?? null)) {
            return;
        }
    }

    override async prepareInitialContent(parameters: JsonObject, context: { signal?: AbortSignal } = {}): Promise<void> {
        await super.prepareInitialContent(parameters, context);
        const runtime = this.#requireRuntime();
        runtime.holdInitialReveal();
        await runtime.prepareInitialContent(context.signal ?? null);
    }

    override async afterPageReveal(context: { signal?: AbortSignal } = {}): Promise<void> {
        await super.afterPageReveal(context);
        if (context.signal?.aborted) {
            return;
        }
        this.#requireRuntime().releaseInitialReveal();
    }

    bindPageEvents(): void {
        const runtime = this.#requireRuntime();
        const signal = this.pageLifecycle.beginListeners();
        const container = this.pageDom.requireHTMLElement(`[data-section="${PAGE_ID}"]`);
        const headerActionsRoot = this.pageDom.requireHTMLElement('.page-header-panel', container);
        this.#pathEditController = new InlineTextEditController({
            elements: {
                trigger: runtime.ui.breadcrumb,
                input: runtime.ui.currentPathInput,
                saveButton: runtime.ui.currentPathSaveButton
            },
            readValue: () => runtime.dataController.getDisplayPath(),
            normalizeValue: (value) => value,
            save: async (value) => {
                const path = runtime.dataController.resolveEnteredPath(value);
                if (path === null) {
                    throw new Error('File Explorer path is empty');
                }
                await runtime.navigatePath(path);
            },
            handleSaveError: () => this.feedback.show(i18n.t('fileExplorer.errors.pathInvalid'), 'error')
        });
        this.#bindModalState(runtime, signal);
        this.#bindHeaderActions(runtime, headerActionsRoot, signal);
        this.#bindListingInteractions(runtime, signal);
    }

    #bindModalState(runtime: ReturnType<typeof createFileExplorerPageRuntime>, signal: AbortSignal): void {
        const modalPresenter = requireModalPresenter();
        let openModalCount = modalPresenter.isOpen(CONTENT_PREVIEW_MODAL_ID) || modalPresenter.isOpen(FILE_EXPLORER_METADATA_MODAL_ID) ? 1 : 0;
        const syncModalState = (event: Event): void => {
            if (event.type === 'core.modal.open') {
                openModalCount += 1;
            } else {
                openModalCount = Math.max(0, openModalCount - 1);
            }
            runtime.setModalOpen(openModalCount > 0);
        };
        const documentRef = dom.getDocument();
        documentRef.addEventListener('core.modal.open', syncModalState, { signal });
        documentRef.addEventListener('core.modal.close', syncModalState, { signal });
        runtime.setModalOpen(openModalCount > 0);
    }

    #bindHeaderActions(runtime: ReturnType<typeof createFileExplorerPageRuntime>, headerActionsRoot: HTMLElement, signal: AbortSignal): void {
        bindPageActionDispatcher({
            root: headerActionsRoot,
            signal,
            label: 'FileExplorerPage.header',
            isAction: isFileexplorerActionId,
            events: {
                click: {
                    mouseButton: 'primary',
                    preventDefault: 'never',
                    ignoreFormControls: true,
                    onAction: ({ event, action, actionElement }): void => {
                        this.#handleHeaderClick(runtime, event, action, actionElement);
                    }
                },
                change: {
                    preventDefault: 'never',
                    onAction: ({ action, actionElement }): void => {
                        if (!isFileExplorerChangeActionId(action)) return;
                        runtime.interactionController.dispatchRootChange(action, actionElement);
                    }
                }
            }
        });
        headerActionsRoot.addEventListener(
            'input',
            (event) => {
                if (this.#pathEditController?.isTarget(event.target)) {
                    this.#pathEditController.handleInput();
                }
            },
            { signal }
        );
        headerActionsRoot.addEventListener(
            'keydown',
            (event) => {
                if (event instanceof KeyboardEvent && this.#pathEditController?.isTarget(event.target)) {
                    this.#pathEditController.handleKeydown(event);
                }
            },
            { signal }
        );
        headerActionsRoot.addEventListener(
            'focusout',
            (event) => {
                if (event instanceof FocusEvent && this.#pathEditController?.isTarget(event.target)) {
                    this.#pathEditController.handleBlur(event);
                }
            },
            { signal }
        );
    }

    #handleHeaderClick(runtime: ReturnType<typeof createFileExplorerPageRuntime>, event: Event, action: string, actionElement: HTMLElement): void {
        if (shouldPreventDefaultForActionElement(actionElement)) event.preventDefault();
        if (action === FILE_EXPLORER_ACTION_NAVIGATE_HOME) {
            terminateHandledPromise(runtime.navigateHome());
            return;
        }
        if (action === FILE_EXPLORER_ACTION_NAVIGATE_PREVIOUS) {
            terminateHandledPromise(runtime.navigatePrevious());
            return;
        }
        if (action === FILE_EXPLORER_ACTION_NAVIGATE_NEXT) {
            terminateHandledPromise(runtime.navigateNext());
            return;
        }
        if (action === FILE_EXPLORER_ACTION_NAVIGATE_UP) {
            terminateHandledPromise(runtime.navigateUp());
            return;
        }
        if (action === FILE_EXPLORER_ACTION_NAVIGATE_PATH) {
            terminateHandledPromise(runtime.navigatePath(this.#requireBreadcrumbPath(actionElement)));
            return;
        }
        if (action === FILE_EXPLORER_ACTION_PATH_EDIT_START) {
            this.#pathEditController?.start();
            return;
        }
        if (action === FILE_EXPLORER_ACTION_PATH_EDIT_SAVE) {
            const pathEditController = this.#pathEditController;
            if (pathEditController) terminateHandledPromise(pathEditController.save());
            return;
        }
        runtime.interactionController.dispatchRootClick(action, actionElement);
    }

    #requireBreadcrumbPath(actionElement: HTMLElement): string {
        const path = actionElement.dataset['path'];
        if (!path) {
            throw new Error('File Explorer breadcrumb crumb is missing its data-path');
        }
        return path;
    }

    #bindListingInteractions(runtime: ReturnType<typeof createFileExplorerPageRuntime>, signal: AbortSignal): void {
        const handleSortSelectChange = (): void => {
            terminateHandledPromise(runtime.applyCurrentSortSelection());
        };
        runtime.ui.sortSelect.addEventListener('change', handleSortSelectChange, { signal });
        const handleListingScroll = (): void => {
            const rowsBody = runtime.ui.rowsBody;
            const edges = measureScrollEdges({
                position: rowsBody.scrollTop,
                extent: rowsBody.scrollHeight,
                viewport: rowsBody.clientHeight,
                tolerance: 1
            });
            if (edges.atEnd) terminateHandledPromise(runtime.loadNextPage());
        };
        runtime.ui.rowsBody.addEventListener('scroll', handleListingScroll, { signal, passive: true });
        bindPageActionDispatcher({
            root: runtime.ui.root,
            signal,
            label: 'FileExplorerPage.root',
            isAction: isFileexplorerActionId,
            events: {
                click: {
                    mouseButton: 'primary',
                    preventDefault: 'never',
                    ignoreFormControls: true,
                    onAction: ({ action, actionElement }): void => {
                        if (!isFileExplorerClickActionId(action)) return;
                        if (runtime.ui.rowsBody.contains(actionElement)) runtime.clearDeeplinkHighlight();
                        if (action === FILE_EXPLORER_ACTION_CLEAR_HIGHLIGHT) return;
                        runtime.interactionController.dispatchRootClick(action, actionElement);
                    }
                },
                change: {
                    preventDefault: 'never',
                    onAction: ({ action, actionElement }): void => {
                        if (!isFileExplorerChangeActionId(action)) return;
                        if (runtime.ui.rowsBody.contains(actionElement)) runtime.clearDeeplinkHighlight();
                        runtime.interactionController.dispatchRootChange(action, actionElement);
                    }
                }
            }
        });
    }

    override async onDestroy(): Promise<void> {
        this.pageLifecycle.abortListeners('file-explorer-destroy');
        this.#pathEditController?.dispose();
        this.#pathEditController = null;
        this.#runtime?.destroy();
        this.#runtime = null;
        this.#initialSortState = null;
    }

    #requireRuntime(): ReturnType<typeof createFileExplorerPageRuntime> {
        if (!this.#runtime) {
            throw new Error('File Explorer runtime is unavailable');
        }
        return this.#runtime;
    }
}

export { FileExplorerPage };
