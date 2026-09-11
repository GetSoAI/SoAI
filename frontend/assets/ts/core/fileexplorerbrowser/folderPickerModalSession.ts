/* SoAI - Shared file explorer browser folder picker modal session [frontend/assets/ts/core/fileexplorerbrowser/folderPickerModalSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedTableBodyHtml } from '@core/security/public.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { resolveDelegatedActionElement } from '@core/dom/dataAction.ts';
import { dom } from '@core/dom/dom.ts';
import { readTrimmedInputValue } from '@core/dom/formValues.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import { EMPTY_UI_HTML } from '@core/security/uiHtml.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { renderInlineLoadingStatus } from '@core/ui/loadingStatus.ts';
import { requireSortableHeaders, resolveNextSortState, updateSortableTableIndicators, type SortState } from '@core/ui/tables/sortableTable.ts';
import { FOLDER_PICKER_MODAL_ID, resolveFolderPickerModalElements, resolveFolderPickerModalScaffoldElements, type FolderPickerModalElements } from '@core/fileexplorerbrowser/folderPickerModalDom.ts';
import { initializeFolderPickerBrowser, resolveFolderPickerSelection } from '@core/fileexplorerbrowser/folderPickerModalPaths.ts';
import { DirectoryBrowserController } from '@core/fileexplorerbrowser/service.ts';
import { formatDisplayPath, renderFolderPickerModalMarkup, renderFolderRows, resolveBrowserErrorMessage, resolveFolderPickerStatusText, sortEntriesByName } from '@core/fileexplorerbrowser/folderPickerView.ts';
import { createFolderPickerModalManualPathController } from '@core/fileexplorerbrowser/folderPickerModalManualPathController.ts';
import type { FolderPickerModalOptions, FolderPickerResult } from '@core/fileexplorerbrowser/folderPickerModalContracts.ts';
import { runModalSession } from '@core/modals/modalSession.ts';
import { resolveVirtualPathFromAbsolute } from '@core/fileexplorerbrowser/paths.ts';

type FolderPickerSessionDependencies = {
    presenter: ModalPresenterApi;
    options: FolderPickerModalOptions;
};

const runFolderPickerModalSession = async (dependencies: FolderPickerSessionDependencies): Promise<FolderPickerResult | null> => {
    const { presenter, options } = dependencies;
    const modalId = FOLDER_PICKER_MODAL_ID;

    return await runModalSession<FolderPickerResult | null>({
        presenter,
        modalId,
        onAlreadyOpen: 'replace',
        initialResult: null,
        initialize: ({ modal, signal, setResult, close }): { dispose: () => void } => {
            const { titleElement, bodySlot, footerLeftSlot, footerRightSlot } = resolveFolderPickerModalScaffoldElements(modal);
            titleElement.textContent = options.title;
            modal.setAttribute('aria-label', options.title);

            const emptySlotHtml = EMPTY_UI_HTML;
            const clearScaffoldSlots = (): void => {
                dom.setHTML(bodySlot, emptySlotHtml, { escape: false });
                dom.setHTML(footerLeftSlot, emptySlotHtml, { escape: false });
                dom.setHTML(footerRightSlot, emptySlotHtml, { escape: false });
            };

            const markup = renderFolderPickerModalMarkup({
                modalId,
                labels: options.labels,
                nameColumnLabel: i18n.t('fileExplorer.table.name'),
                hostMode: options.source.type === 'host',
                ...(options.allowManualPathEntry === true ? { allowManualPathEntry: true } : {})
            });

            dom.setHTML(bodySlot, markup.body, { escape: false });
            dom.setHTML(footerLeftSlot, markup.footerLeft, { escape: false });
            dom.setHTML(footerRightSlot, markup.footerRight, { escape: false });

            let elements: FolderPickerModalElements;
            try {
                elements = resolveFolderPickerModalElements(modal, Boolean(options.labels.reset), options.source.type === 'host');
            } catch (error) {
                clearScaffoldSlots();
                throw error;
            }
            const { currentPathElement, rootSelect, statusElement, tableElement, rowsElement, sortHeaderElement, searchInput, manualInput, confirmButton, cancelButton, resetButton } = elements;

            let sortState: SortState<'name'> = { column: 'name', direction: 'asc' };
            let lastRenderedDisplayPath = '';
            let manualPathController: ReturnType<typeof createFolderPickerModalManualPathController> | null = null;
            let renderedRoots: readonly string[] = [];
            let confirmationPending = false;
            const sortHeaders = requireSortableHeaders(tableElement, 'Folder picker');

            const updateSortIndicator = (): void => {
                updateSortableTableIndicators({ headers: sortHeaders, activeColumn: sortState.column, activeDirection: sortState.direction, host: { getIconSync } });
            };

            const toggleSort = (): void => {
                sortState = resolveNextSortState(sortState, 'name', 'asc');
                updateSortIndicator();
                renderRows();
            };

            const renderRows = (): void => {
                const state = browser.getState();
                const sortedEntries = sortEntriesByName(state.entries, sortState.direction);
                const rowsMarkup = toTrustedTableBodyHtml(renderFolderRows(sortedEntries, state.currentPath, options.labels, getIconSync));
                dom.setHTML(rowsElement, rowsMarkup, { escape: false });
            };

            const updateConfirmButton = (): void => {
                const state = browser.getState();
                const override = manualPathController ? manualPathController.getStatusOverrideMessage() : null;
                confirmButton.disabled = confirmationPending || state.isLoading || !state.canConfirm || Boolean(override);
            };

            const syncRootSelector = (): void => {
                if (!rootSelect) return;
                const state = browser.getState();
                if (renderedRoots !== state.rootPaths) {
                    rootSelect.replaceChildren(
                        ...state.rootPaths.map((rootPath) => {
                            const option = document.createElement('option');
                            option.value = rootPath;
                            option.textContent = rootPath;
                            return option;
                        })
                    );
                    renderedRoots = state.rootPaths;
                }
                const activeRoot = state.pendingRootPath ?? state.workspacePathResolved;
                rootSelect.value = state.rootPaths.find((rootPath) => activeRoot !== null && resolveVirtualPathFromAbsolute(rootPath, activeRoot) === '/') ?? activeRoot ?? '';
                rootSelect.disabled = state.rootPaths.length === 0;
            };

            const syncStatus = (): void => {
                const override = manualPathController ? manualPathController.getStatusOverrideMessage() : null;
                const state = browser.getState();
                renderInlineLoadingStatus(statusElement, {
                    text: resolveFolderPickerStatusText(state, options.labels, override),
                    loading: state.isLoading && override === null && state.errorMessage === null
                });
            };

            const browser = new DirectoryBrowserController({
                source: options.source,
                entryFilter: (entry) => entry.isDirectory,
                errorResolver: { resolve: resolveBrowserErrorMessage },
                onStateChange: (state) => {
                    const displayPath = options.source.type === 'host' && state.workspacePathResolved === null ? '' : formatDisplayPath(state.currentPath, state.workspacePathResolved);
                    currentPathElement.value = displayPath;
                    if (manualPathController) {
                        manualPathController.handleBrowserStateChange(displayPath);
                    } else {
                        lastRenderedDisplayPath = displayPath;
                        if (options.allowManualPathEntry === true) {
                            manualInput.value = displayPath;
                        }
                    }
                    syncStatus();
                    syncRootSelector();
                    renderRows();
                    updateConfirmButton();
                }
            });

            const manualPath = createFolderPickerModalManualPathController({
                browser,
                manualInput,
                allowManualPathEntry: options.allowManualPathEntry === true,
                labels: options.labels,
                syncStatus,
                updateConfirmButton,
                getLastRenderedDisplayPath: () => lastRenderedDisplayPath,
                setLastRenderedDisplayPath: (value: string) => {
                    lastRenderedDisplayPath = value;
                }
            });
            manualPathController = manualPath;

            const dispose = (): void => {
                browser.destroy();
                clearScaffoldSlots();
            };

            const closeWith = (nextResult: FolderPickerResult | null, reason: string): void => {
                setResult(nextResult);
                close(reason);
            };

            const handleTableClick = (event: Event): void => {
                const actionElement = resolveDelegatedActionElement({ event, root: tableElement, preventDefault: 'never' });
                if (!actionElement) {
                    return;
                }
                const action = actionElement.dataset['action'];
                if (!action) {
                    return;
                }
                if (action === 'folder-picker-sort') {
                    toggleSort();
                    return;
                }
                if (action === 'folder-picker-open' || action === 'folder-picker-up') {
                    const path = actionElement.dataset['path'];
                    if (!path) {
                        throw new Error('Folder picker action is missing required data-path');
                    }
                    manualPath.resetTracking();
                    terminateHandledPromise(browser.navigate(path));
                }
            };

            tableElement.addEventListener('click', handleTableClick, { signal });
            sortHeaderElement.addEventListener(
                'keydown',
                (event: KeyboardEvent) => {
                    if (event.key !== 'Enter' && event.key !== ' ') {
                        return;
                    }
                    event.preventDefault();
                    toggleSort();
                },
                { signal }
            );

            searchInput.addEventListener(
                'input',
                () => {
                    const value = readTrimmedInputValue(searchInput);
                    manualPath.resetTracking();
                    void (value ? browser.search(value) : browser.clearSearch());
                },
                { signal }
            );

            manualInput.addEventListener('input', manualPath.handleManualInputEvent, { signal });
            manualInput.addEventListener('keydown', manualPath.handleManualKeydown, { signal });

            rootSelect?.addEventListener(
                'change',
                () => {
                    manualPath.resetTracking();
                    terminateHandledPromise(browser.changeRoot(rootSelect.value));
                },
                { signal }
            );

            const handleCancelClick = (event: Event): void => {
                event.preventDefault();
                closeWith(null, 'cancel');
            };
            cancelButton.addEventListener('click', handleCancelClick, { signal });

            const confirmFolderSelection = async (): Promise<void> => {
                if (confirmationPending) return;
                confirmationPending = true;
                updateConfirmButton();
                try {
                    if (!(await manualPath.navigateToManualPath())) {
                        return;
                    }
                    if (!(await browser.validateSelection())) {
                        return;
                    }
                    const selection = resolveFolderPickerSelection(browser);
                    closeWith(selection, 'confirm');
                } catch (error) {
                    ensureError(error);
                    manualPath.setStatusOverrideMessage(options.labels.validationFailed);
                } finally {
                    confirmationPending = false;
                    if (!signal.aborted) {
                        updateConfirmButton();
                    }
                }
            };

            const handleConfirmClick = (event: Event): void => {
                event.preventDefault();
                terminateHandledPromise(confirmFolderSelection());
            };
            confirmButton.addEventListener('click', handleConfirmClick, { signal });

            if (resetButton) {
                const handleResetClick = (event: Event): void => {
                    event.preventDefault();
                    closeWith({ resultType: 'reset' }, 'reset');
                };
                resetButton.addEventListener('click', handleResetClick, { signal });
            }

            updateSortIndicator();
            terminateHandledPromise(
                (async (): Promise<void> => {
                    await initializeFolderPickerBrowser({
                        browser,
                        initialVirtualPath: options.initialVirtualPath,
                        initialAbsolutePathToBrowse: options.initialAbsolutePathToBrowse,
                        resetManualInputTracking: () => manualPath.resetTracking()
                    });
                    if (signal.aborted) {
                        return;
                    }
                })()
            );

            return { dispose };
        }
    });
};

export { runFolderPickerModalSession };
