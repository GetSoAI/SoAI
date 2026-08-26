/* SoAI - File explorer page control layer runtime [frontend/assets/ts/pages/fileexplorer/controllers/page/runtime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { toVirtualPath } from '@core/fileexplorerbrowser/paths.ts';
import { consumeRepeatableDropdownSelection } from '@core/ui/dropdown/selectControl.ts';
import { normalizeSearchDisplayQuery } from '@core/search/searchQuery.ts';
import { getWebUiUserCancellationReason } from '@core/tasks/cancellationReasons.ts';
import { isFileExplorerApi } from '@pages/fileexplorer/guards/pageGuards.ts';
import { FileExplorerCommandsController } from '@pages/fileexplorer/controllers/FileExplorerCommandsController.ts';
import { FileExplorerBatchController } from '@pages/fileexplorer/controllers/FileExplorerBatchController.ts';
import { FileExplorerDataController } from '@pages/fileexplorer/controllers/FileExplorerDataController.ts';
import { FileExplorerOperationsController } from '@pages/fileexplorer/controllers/FileExplorerOperationsController.ts';
import { FileExplorerNavigationHistoryController } from '@pages/fileexplorer/controllers/FileExplorerNavigationHistoryController.ts';
import { FileExplorerPageInteractionController } from '@pages/fileexplorer/controllers/FileExplorerPageInteractionController.ts';
import { FileExplorerRecentUploadController } from '@pages/fileexplorer/controllers/FileExplorerRecentUploadController.ts';
import { FileExplorerContentPreviewModalController } from '@pages/fileexplorer/controllers/FileExplorerContentPreviewModalController.ts';
import { FileExplorerTaskProgressController } from '@pages/fileexplorer/controllers/FileExplorerTaskProgressController.ts';
import { FileExplorerViewModeController } from '@pages/fileexplorer/controllers/FileExplorerViewModeController.ts';
import { FileExplorerRowsRevealController } from '@pages/fileexplorer/controllers/fileExplorerRowsRevealController.ts';
import { FileExplorerSelectionModel } from '@pages/fileexplorer/state/FileExplorerSelectionState.ts';
import { createFileExplorerUiTaskScheduler } from '@pages/fileexplorer/controllers/fileExplorerUiTaskSchedulerController.ts';
import { createFileExplorerDeeplinkHighlightController } from '@pages/fileexplorer/controllers/page/deeplinkHighlightController.ts';
import { createFileExplorerDeeplinkPreviewController } from '@pages/fileexplorer/controllers/page/deeplinkPreviewController.ts';
import { FileExplorerInitialContentController } from '@pages/fileexplorer/controllers/page/FileExplorerInitialContentController.ts';
import type { FileExplorerPageRuntime, FileExplorerPageRuntimeHost, FileExplorerRuntimeInitializationOptions } from '@pages/fileexplorer/controllers/page/contracts.ts';
import { persistFileExplorerSortState } from '@pages/fileexplorer/controllers/page/fileExplorerPageControlsController.ts';
import { FileExplorerPageSearchController } from '@pages/fileexplorer/controllers/page/searchController.ts';
import { createFileExplorerControllerHost } from '@pages/fileexplorer/controllers/page/service.ts';
import { requireFileExplorerUi } from '@pages/fileexplorer/dom.ts';
import type { FileExplorerSelectionProvider } from '@pages/fileexplorer/types.ts';

const createFileExplorerPageRuntime = (host: FileExplorerPageRuntimeHost, initialization: FileExplorerRuntimeInitializationOptions): FileExplorerPageRuntime => {
    const ui = requireFileExplorerUi({
        requireHTMLElement: (selector) => host.pageDom.requireHTMLElement(selector),
        optionalHTMLElement: (selector, context) => host.pageDom.optionalHTMLElement(selector, context)
    });
    let disposed = false;
    const uiTaskScheduler = createFileExplorerUiTaskScheduler({
        runWithBoundary: (operationId, task) => host.pageLifecycle.run(operationId, task),
        logWarning: (message, error) => {
            errorHandler.warn('FileExplorer', message, error);
        }
    });
    const deeplinkHighlight = createFileExplorerDeeplinkHighlightController({ rowsBody: ui.rowsBody, highlightPath: initialization.highlightPath });
    const fileExplorerApi = host.api.fileExplorer;
    if (!isFileExplorerApi(fileExplorerApi)) {
        throw new Error('File Explorer page requires file explorer API methods');
    }
    const controllerHost = createFileExplorerControllerHost(fileExplorerApi, {
        awaitTask: host.waitForTask,
        showNotification: (message, type) => host.feedback.show(message, type),
        handleError: (error, context, options = {}) => host.feedback.handle(error, context, { notify: options.notify === true }),
        getIconSync: (name, options) => host.services.getIconSync(name, options)
    });
    const commandsController = new FileExplorerCommandsController({
        ui,
        onSelectionModeChanged: (inSelectionMode) => {
            ui.selectionStatusBadge.classList.toggle('u-hidden', !inSelectionMode);
            ui.root.classList.toggle('is-selection-mode', inSelectionMode);
            host.layout.updatePageActions();
        }
    });
    const taskProgressController = new FileExplorerTaskProgressController({
        ui,
        onCancelTask: async (taskId: string): Promise<void> => {
            await host.api.system.cancelTask(taskId, getWebUiUserCancellationReason());
        }
    });
    taskProgressController.initialize();
    const rowsRevealController = new FileExplorerRowsRevealController({
        root: ui.root,
        rowsBody: ui.rowsBody
    });
    const recentUploadController = new FileExplorerRecentUploadController();
    let selectionRenderer: (() => void) | null = null;
    const selectionModel = new FileExplorerSelectionModel({ onChange: () => selectionRenderer?.() });

    let navigationHistoryController: FileExplorerNavigationHistoryController | null = null;
    const dataController = new FileExplorerDataController({
        host: controllerHost,
        ui,
        initialSort: initialization.sortState,
        persistSort: (state) => persistFileExplorerSortState(host.storage, state),
        recentUploads: recentUploadController,
        selection: selectionModel,
        rowsReveal: rowsRevealController,
        onStateChanged: (currentPath, isLoading) => {
            navigationHistoryController?.handleBrowserState(currentPath, isLoading);
            deeplinkHighlight.apply();
        },
        onRowsCommitted: () => deeplinkHighlight.apply()
    });
    const viewModeController = new FileExplorerViewModeController({
        root: ui.root,
        button: ui.viewModeToggleButton,
        sortSelect: ui.sortSelect,
        sortShell: ui.sortShell,
        getIconSync: (name, options) => host.services.getIconSync(name, options),
        labels: {
            list: i18n.t('fileExplorer.actions.listView'),
            icons: i18n.t('fileExplorer.actions.iconView')
        },
        prepareCollectionViewModeChange: () => dataController.prepareForViewModeChange(),
        reapplyCollection: () => dataController.reapplyAfterViewModeChange(),
        onActionsChanged: () => host.layout.updatePageActions()
    });
    selectionRenderer = (): void => {
        dataController.syncSelectionRows();
        commandsController.applySelectionView(selectionModel.view());
    };
    const searchController = new FileExplorerPageSearchController({
        requireHTMLElement: (selector) => host.pageDom.requireHTMLElement(selector),
        createStandardSearch: (container, options) => host.layout.createSearch(container, options),
        runUiTask: (operation, task) => uiTaskScheduler.runAsync(operation, task),
        search: (query) => dataController.search(query),
        clearSearch: () => dataController.clearSearch(),
        isDisposed: () => disposed
    });
    const resetSearchOnNavigation = (): void => searchController.resetOnNavigation();
    navigationHistoryController = new FileExplorerNavigationHistoryController({
        host: {
            navigate: (path) => dataController.navigate(path),
            resetSearchOnNavigation
        },
        buttons: {
            home: ui.navigateHomeButton,
            previous: ui.navigatePreviousButton,
            next: ui.navigateNextButton,
            up: ui.navigateUpButton
        }
    });
    const navigationHistory = navigationHistoryController;

    const selection: FileExplorerSelectionProvider = {
        getCurrentPath: () => dataController.getCurrentPath(),
        getSelectedPaths: () => selectionModel.getSelectedPaths(),
        refresh: async (uploadSession) => {
            await dataController.refreshList();
            if (uploadSession) await recentUploadController.revealPending(uploadSession, (path) => dataController.revealPath(path));
        }
    };
    const operationsController = new FileExplorerOperationsController({
        host: controllerHost,
        ui,
        selection,
        recentUploads: recentUploadController
    });
    const batchController = new FileExplorerBatchController({
        host: controllerHost,
        selection
    });
    const contentPreviewModalController = new FileExplorerContentPreviewModalController({
        requireHTMLElement: (selector, context) => host.pageDom.requireHTMLElement(selector, context),
        modalPresenter: host.modalPresenter,
        showNotification: (message, type) => host.feedback.show(message, type),
        readPath: (path) => dataController.readPath(path),
        loadMetadata: (path) => dataController.loadMetadata(path),
        downloadResponse: async (path) => controllerHost.api.download(toVirtualPath(path)),
        downloadPath: (path) => operationsController.downloadPath(path),
        writeFile: (path, content) => operationsController.writeFile(path, content),
        createFile: (path, content) => operationsController.createFile(path, content),
        movePath: (sourcePath, destinationPath) => operationsController.movePath(sourcePath, destinationPath),
        getCurrentFolderImagePaths: () => dataController.getCurrentFolderImagePaths(),
        runWithBoundary: (operation, task) => host.pageLifecycle.run(operation, task)
    });
    const interactionController = new FileExplorerPageInteractionController({
        host: {
            showNotification: (message, type) => host.feedback.show(message, type),
            requireHTMLElement: (selector, context) => host.pageDom.requireHTMLElement(selector, context),
            modalPresenter: host.modalPresenter,
            runUiTask: (operation, task) => uiTaskScheduler.runAsync(operation, task)
        },
        data: dataController,
        selection: selectionModel,
        operations: operationsController,
        batch: batchController,
        commands: commandsController,
        taskProgress: taskProgressController,
        contentPreviewModal: contentPreviewModalController,
        viewMode: viewModeController,
        navigationHistory
    });

    const initialSearch = normalizeSearchDisplayQuery(initialization.searchQuery);
    const deeplinkPreview = createFileExplorerDeeplinkPreviewController({ previewPath: initialization.previewPath, isDisposed: () => disposed, openPreview: (path) => contentPreviewModalController.show(path) });
    const initialContentController = new FileExplorerInitialContentController({
        initialPath: initialization.initialPath,
        highlightPath: initialization.highlightPath,
        initialSearch,
        isDisposed: () => disposed,
        runTask: (task) => host.pageLifecycle.run('fileExplorer:initialLoad', task),
        initialize: (path) => dataController.initialize(path),
        revealPath: (path) => dataController.revealPath(path),
        applyInitialSearch: (query) => searchController.applyInitialSearch(query),
        openPreview: () => deeplinkPreview.open()
    });
    const navigateHome = async (): Promise<void> => {
        if (disposed) {
            return;
        }
        await uiTaskScheduler.runAsync('fileExplorer:navigate:home', async () => {
            if (disposed) {
                return;
            }
            await navigationHistory.navigateHome();
        });
    };
    const navigatePrevious = async (): Promise<void> => {
        await uiTaskScheduler.runAsync('fileExplorer:navigate:previous', async () => {
            if (disposed) {
                return;
            }
            await navigationHistory.navigatePrevious();
        });
    };
    const navigateNext = async (): Promise<void> => {
        await uiTaskScheduler.runAsync('fileExplorer:navigate:next', async () => {
            if (disposed) {
                return;
            }
            await navigationHistory.navigateNext();
        });
    };
    const navigateUp = async (): Promise<void> => {
        await uiTaskScheduler.runAsync('fileExplorer:navigate:up', async () => {
            if (disposed) {
                return;
            }
            await navigationHistory.navigateUp();
        });
    };
    const navigatePath = async (path: string): Promise<void> => {
        await uiTaskScheduler.runAsync('fileExplorer:navigate:path', async () => {
            if (disposed) {
                return;
            }
            await navigationHistory.navigate(path);
        });
    };
    const applyCurrentSortSelection = async (): Promise<void> => {
        const requestedColumn = consumeRepeatableDropdownSelection(ui.sortSelect);
        await uiTaskScheduler.runAsync('fileExplorer:change:fileExplorer.sort', async () => {
            if (disposed) {
                return;
            }
            await dataController.sort(requestedColumn);
        });
    };
    const loadNextPage = async (): Promise<void> => {
        await uiTaskScheduler.runAsync('fileExplorer:listing:next', async () => {
            if (disposed) return;
            await dataController.loadNextPage();
        });
    };

    return {
        ui,
        dataController,
        operationsController,
        interactionController,
        prepareInitialContent: (signal) => initialContentController.prepare(signal),
        holdInitialReveal: () => rowsRevealController.holdRelease(),
        releaseInitialReveal: () => {
            rowsRevealController.releaseNow();
            rowsRevealController.resumeAutoRelease();
        },
        navigateHome,
        navigatePrevious,
        navigateNext,
        navigateUp,
        navigatePath,
        applyCurrentSortSelection,
        loadNextPage,
        setModalOpen: (modalOpen: boolean) => commandsController.setModalOpen(modalOpen),
        resetSearchOnNavigation,
        clearDeeplinkHighlight: deeplinkHighlight.clear,
        destroy: () => {
            disposed = true;
            uiTaskScheduler.dispose();
            interactionController.destroy();
            navigationHistory.destroy();
            batchController.destroy();
            operationsController.destroy();
            recentUploadController.clear();
            deeplinkHighlight.clear();
            deeplinkPreview.clear();
            contentPreviewModalController.dispose();
            taskProgressController.destroy();
            commandsController.destroy();
            rowsRevealController.dispose();
            dataController.destroy();
        }
    };
};

export { createFileExplorerPageRuntime };
export type { FileExplorerPageRuntime, FileExplorerPageRuntimeHost };
