/* SoAI - Shared file explorer browser folder picker modal paths [frontend/assets/ts/core/fileexplorerbrowser/folderPickerModalPaths.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parentVirtualPath, resolveAbsolutePath, resolveVirtualPathFromAbsolute, toVirtualPath } from '@core/fileexplorerbrowser/paths.ts';
import { DirectoryBrowserController } from '@core/fileexplorerbrowser/service.ts';

type FolderPickerSelectionResult = {
    resultType: 'selected';
    virtualPath: string;
    absolutePath: string | null;
    workspacePathResolved: string | null;
};

type InitializeFolderPickerBrowserOptions = {
    browser: DirectoryBrowserController;
    initialVirtualPath: string | undefined;
    initialAbsolutePathToBrowse: string | undefined;
    resetManualInputTracking: () => void;
};

const resolveFolderPickerSelection = (browser: DirectoryBrowserController): FolderPickerSelectionResult => {
    const state = browser.getState();
    return {
        resultType: 'selected',
        virtualPath: state.currentPath,
        absolutePath: resolveAbsolutePath(state.workspacePathResolved, state.currentPath),
        workspacePathResolved: state.workspacePathResolved
    };
};

const initializeFolderPickerBrowser = async (options: InitializeFolderPickerBrowserOptions): Promise<void> => {
    const initialVirtualPath = options.initialVirtualPath ? toVirtualPath(options.initialVirtualPath) : '/';
    options.resetManualInputTracking();
    if (options.browser.getSourceType() === 'host') {
        await options.browser.initialize(options.initialAbsolutePathToBrowse ? { initialAbsolutePath: options.initialAbsolutePathToBrowse } : {});
        return;
    }
    await options.browser.initialize({ initialVirtualPath });
    if (options.browser.getState().errorMessage && initialVirtualPath !== '/') {
        options.resetManualInputTracking();
        await options.browser.navigate('/');
    }
    if (!options.initialAbsolutePathToBrowse) {
        return;
    }
    const workspacePathResolved = options.browser.getState().workspacePathResolved;
    if (!workspacePathResolved) {
        return;
    }
    const mappedVirtualPath = resolveVirtualPathFromAbsolute(workspacePathResolved, options.initialAbsolutePathToBrowse);
    if (!mappedVirtualPath || mappedVirtualPath === options.browser.getState().currentPath) {
        return;
    }
    let candidatePath = mappedVirtualPath;
    while (true) {
        options.resetManualInputTracking();
        await options.browser.navigate(candidatePath);
        if (!options.browser.getState().errorMessage) {
            return;
        }
        if (candidatePath === '/') {
            return;
        }
        const nextCandidatePath = parentVirtualPath(candidatePath);
        if (nextCandidatePath === candidatePath) {
            return;
        }
        candidatePath = nextCandidatePath;
    }
};

export { initializeFolderPickerBrowser, resolveFolderPickerSelection };
export type { FolderPickerSelectionResult, InitializeFolderPickerBrowserOptions };
