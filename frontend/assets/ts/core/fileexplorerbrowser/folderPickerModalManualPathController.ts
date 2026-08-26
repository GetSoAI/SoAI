/* SoAI - Shared file explorer browser folder picker modal manual path controller [frontend/assets/ts/core/fileexplorerbrowser/folderPickerModalManualPathController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { readTrimmedInputValue } from '@core/dom/formValues.ts';
import { formatDisplayPath, type FolderPickerLabels } from '@core/fileexplorerbrowser/folderPickerView.ts';
import { isAbsoluteOsPath, resolveVirtualPathFromAbsolute } from '@core/fileexplorerbrowser/paths.ts';
import { DirectoryBrowserController } from '@core/fileexplorerbrowser/service.ts';

type FolderPickerManualPathController = {
    handleBrowserStateChange: (displayPath: string) => void;
    handleManualInputEvent: () => void;
    handleManualKeydown: (event: Event) => void;
    navigateToManualPath: () => Promise<boolean>;
    resetTracking: () => void;
    setStatusOverrideMessage: (message: string | null) => void;
    getStatusOverrideMessage: () => string | null;
    getManualAbsoluteSelection: () => string | null;
};

type FolderPickerManualPathControllerDependencies = {
    browser: DirectoryBrowserController;
    manualInput: HTMLInputElement;
    allowManualPathEntry: boolean;
    allowManualAbsoluteSelectionOutsideRoot: boolean;
    labels: FolderPickerLabels;
    syncStatus: () => void;
    updateConfirmButton: () => void;
    getLastRenderedDisplayPath: () => string;
    setLastRenderedDisplayPath: (value: string) => void;
};

const createFolderPickerModalManualPathController = (dependencies: FolderPickerManualPathControllerDependencies): FolderPickerManualPathController => {
    const { browser, manualInput, allowManualPathEntry, allowManualAbsoluteSelectionOutsideRoot, labels, syncStatus, updateConfirmButton, getLastRenderedDisplayPath, setLastRenderedDisplayPath } = dependencies;
    let manualInputDirty = false;
    let statusOverrideMessage: string | null = null;
    let manualAbsoluteSelection: string | null = null;

    const resetTracking = (): void => {
        manualInputDirty = false;
        statusOverrideMessage = null;
        manualAbsoluteSelection = null;
    };

    const getStatusOverrideMessage = (): string | null => statusOverrideMessage;

    const setStatusOverrideMessage = (message: string | null): void => {
        statusOverrideMessage = message;
        syncStatus();
        updateConfirmButton();
    };

    const getManualAbsoluteSelection = (): string | null => manualAbsoluteSelection;

    const handleBrowserStateChange = (displayPath: string): void => {
        setLastRenderedDisplayPath(displayPath);
        if (allowManualPathEntry !== true || manualInputDirty) {
            return;
        }
        manualAbsoluteSelection = null;
        manualInput.value = displayPath;
    };

    const handleManualInputEvent = (): void => {
        manualInputDirty = readTrimmedInputValue(manualInput) !== getLastRenderedDisplayPath();
        manualAbsoluteSelection = null;
        if (allowManualPathEntry !== true || !statusOverrideMessage) {
            return;
        }
        statusOverrideMessage = null;
        syncStatus();
        updateConfirmButton();
    };

    const navigateToManualPath = async (): Promise<boolean> => {
        if (allowManualPathEntry !== true) {
            return true;
        }
        manualAbsoluteSelection = null;
        const targetPath = readTrimmedInputValue(manualInput);
        const browserState = browser.getState();
        const displayedPath = formatDisplayPath(browserState.currentPath, browserState.workspacePathResolved);
        if (!targetPath || targetPath === displayedPath) {
            manualInputDirty = false;
            statusOverrideMessage = null;
            manualAbsoluteSelection = null;
            syncStatus();
            return true;
        }
        if (!isAbsoluteOsPath(targetPath)) {
            setStatusOverrideMessage(labels.manualAbsolutePathRequired);
            return false;
        }
        const workspacePathResolved = browserState.workspacePathResolved;
        if (!workspacePathResolved) {
            if (allowManualAbsoluteSelectionOutsideRoot === true) {
                manualAbsoluteSelection = targetPath;
                statusOverrideMessage = null;
                syncStatus();
                updateConfirmButton();
                return true;
            }
            setStatusOverrideMessage(labels.loadFailed);
            return false;
        }
        const mappedVirtualPath = resolveVirtualPathFromAbsolute(workspacePathResolved, targetPath);
        if (!mappedVirtualPath) {
            if (allowManualAbsoluteSelectionOutsideRoot === true) {
                manualAbsoluteSelection = targetPath;
                statusOverrideMessage = null;
                syncStatus();
                updateConfirmButton();
                return true;
            }
            setStatusOverrideMessage(labels.manualAbsolutePathRequired);
            return false;
        }
        manualAbsoluteSelection = null;
        statusOverrideMessage = null;
        syncStatus();
        await browser.navigate(mappedVirtualPath);
        if (!browser.getState().errorMessage) {
            manualInputDirty = false;
            manualInput.value = getLastRenderedDisplayPath();
            return true;
        }
        manualInputDirty = true;
        return false;
    };

    const handleManualKeydown = (event: Event): void => {
        if (!(event instanceof KeyboardEvent)) {
            return;
        }
        if (event.key !== 'Enter') {
            return;
        }
        event.preventDefault();
        terminateHandledPromise(navigateToManualPath());
    };

    return {
        handleBrowserStateChange,
        handleManualInputEvent,
        handleManualKeydown,
        navigateToManualPath,
        resetTracking,
        setStatusOverrideMessage,
        getStatusOverrideMessage,
        getManualAbsoluteSelection
    };
};

export { createFolderPickerModalManualPathController };
export type { FolderPickerManualPathController };
