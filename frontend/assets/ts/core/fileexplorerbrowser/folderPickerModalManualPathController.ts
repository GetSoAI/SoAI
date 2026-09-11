/* SoAI - Shared file explorer browser folder picker modal manual path controller [frontend/assets/ts/core/fileexplorerbrowser/folderPickerModalManualPathController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { readTrimmedInputValue } from '@core/dom/formValues.ts';
import { formatDisplayPath, type FolderPickerLabels } from '@core/fileexplorerbrowser/folderPickerView.ts';
import { resolveVirtualPathFromAbsolute } from '@core/fileexplorerbrowser/paths.ts';
import { DirectoryBrowserController } from '@core/fileexplorerbrowser/service.ts';
import { isAbsoluteFilesystemPath } from '@core/filePathResolution.ts';

type FolderPickerManualPathController = {
    handleBrowserStateChange: (displayPath: string) => void;
    handleManualInputEvent: () => void;
    handleManualKeydown: (event: Event) => void;
    navigateToManualPath: () => Promise<boolean>;
    resetTracking: () => void;
    setStatusOverrideMessage: (message: string | null) => void;
    getStatusOverrideMessage: () => string | null;
};

type FolderPickerManualPathControllerDependencies = {
    browser: DirectoryBrowserController;
    manualInput: HTMLInputElement;
    allowManualPathEntry: boolean;
    labels: FolderPickerLabels;
    syncStatus: () => void;
    updateConfirmButton: () => void;
    getLastRenderedDisplayPath: () => string;
    setLastRenderedDisplayPath: (value: string) => void;
};

const createFolderPickerModalManualPathController = (dependencies: FolderPickerManualPathControllerDependencies): FolderPickerManualPathController => {
    const { browser, manualInput, allowManualPathEntry, labels, syncStatus, updateConfirmButton, getLastRenderedDisplayPath, setLastRenderedDisplayPath } = dependencies;
    let manualInputDirty = false;
    let statusOverrideMessage: string | null = null;

    const resetTracking = (): void => {
        manualInputDirty = false;
        statusOverrideMessage = null;
    };

    const getStatusOverrideMessage = (): string | null => statusOverrideMessage;

    const setStatusOverrideMessage = (message: string | null): void => {
        statusOverrideMessage = message;
        syncStatus();
        updateConfirmButton();
    };

    const handleBrowserStateChange = (displayPath: string): void => {
        setLastRenderedDisplayPath(displayPath);
        if (allowManualPathEntry !== true || manualInputDirty) {
            return;
        }
        manualInput.value = displayPath;
    };

    const handleManualInputEvent = (): void => {
        manualInputDirty = readTrimmedInputValue(manualInput) !== getLastRenderedDisplayPath();
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
        const targetPath = readTrimmedInputValue(manualInput);
        const browserState = browser.getState();
        const displayedPath = formatDisplayPath(browserState.currentPath, browserState.workspacePathResolved);
        if (!targetPath || targetPath === displayedPath) {
            manualInputDirty = false;
            statusOverrideMessage = null;
            syncStatus();
            return true;
        }
        if (!isAbsoluteFilesystemPath(targetPath)) {
            setStatusOverrideMessage(labels.manualAbsolutePathRequired);
            return false;
        }
        if (browser.getSourceType() === 'host') {
            statusOverrideMessage = null;
            syncStatus();
            const located = await browser.locate(targetPath);
            if (located) {
                manualInputDirty = false;
                manualInput.value = getLastRenderedDisplayPath();
                return true;
            }
            manualInputDirty = true;
            return false;
        }
        const workspacePathResolved = browserState.workspacePathResolved;
        if (!workspacePathResolved) {
            setStatusOverrideMessage(labels.loadFailed);
            return false;
        }
        const mappedVirtualPath = resolveVirtualPathFromAbsolute(workspacePathResolved, targetPath);
        if (!mappedVirtualPath) {
            setStatusOverrideMessage(labels.validationFailed);
            return false;
        }
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
        getStatusOverrideMessage
    };
};

export { createFolderPickerModalManualPathController };
export type { FolderPickerManualPathController };
