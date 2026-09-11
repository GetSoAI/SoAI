/* SoAI - Shared owner-scoped workspace path draft and folder selection [frontend/assets/ts/core/fileexplorerbrowser/workspacePathDraft.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { buildFolderPickerLabels } from '@core/fileexplorerbrowser/folderPickerLabels.ts';
import { showFolderPickerModal, type FolderPickerResult } from '@core/fileexplorerbrowser/folderPickerModal.ts';
import { resolveFolderPickerPathOverride } from '@core/fileexplorerbrowser/folderPickerPathOverride.ts';
import { resolveAbsolutePath } from '@core/fileexplorerbrowser/paths.ts';
import { isAbsoluteFilesystemPath } from '@core/filePathResolution.ts';
import type { WorkspaceBrowserAccess } from '@core/fileexplorerbrowser/workspaceBrowserAccess.ts';
import { toTrimmedString } from '@core/normalize.ts';

interface WorkspacePathPickerStrings {
    title: string;
    message: string;
    chooseCurrent: string;
}

const resolveWorkspaceSelection = (result: FolderPickerResult): string | null | undefined => {
    if (result.resultType !== 'selected') return undefined;
    const absolutePath = toTrimmedString(result.absolutePath);
    if (absolutePath) return absolutePath;
    const override = resolveFolderPickerPathOverride(result);
    if (override !== null) return override;
    const virtualPath = toTrimmedString(result.virtualPath);
    return virtualPath || undefined;
};

const resolveWorkspaceDisplayPath = (workspacePath: string | null | undefined, currentWorkspacePath: string): string | null => {
    const fallback = toTrimmedString(currentWorkspacePath);
    const value = toTrimmedString(workspacePath);
    if (!value) return fallback || null;
    if (isAbsoluteFilesystemPath(value)) return value;
    return resolveAbsolutePath(fallback, value) ?? value;
};

class WorkspacePathDraft {
    #workspacePath: string | null = null;
    #displayPath: string | null = null;
    #currentWorkspacePath: string | null = null;

    setValue(workspacePath: string | null | undefined, currentWorkspacePath: string): void {
        this.#currentWorkspacePath = toTrimmedString(currentWorkspacePath) || null;
        this.#workspacePath = toTrimmedString(workspacePath) || null;
        this.#displayPath = resolveWorkspaceDisplayPath(workspacePath, currentWorkspacePath);
    }

    getValue(): string | null {
        return this.#workspacePath;
    }

    getSummary(): string {
        if (this.#displayPath === null) throw new Error('Workspace path is not initialized');
        return this.#displayPath;
    }

    getCurrentWorkspacePath(): string {
        if (this.#currentWorkspacePath === null) throw new Error('Current workspace path is not initialized');
        return this.#currentWorkspacePath;
    }

    async open(options: { access: WorkspaceBrowserAccess; readOnly: boolean; canApply: () => boolean; strings: WorkspacePathPickerStrings }): Promise<boolean> {
        if (options.readOnly) return false;
        const currentPath = this.#displayPath;
        const pathIsAbsolute = currentPath ? isAbsoluteFilesystemPath(currentPath) : false;
        const result = await showFolderPickerModal({
            source: { type: 'workspace', api: options.access.browserApi },
            title: options.strings.title,
            message: options.strings.message,
            labels: buildFolderPickerLabels({ chooseCurrent: options.strings.chooseCurrent }),
            ...(currentPath && pathIsAbsolute ? { initialAbsolutePathToBrowse: currentPath } : {}),
            ...(currentPath && !pathIsAbsolute ? { initialVirtualPath: currentPath } : {}),
            allowManualPathEntry: true
        });
        if (!result || !options.canApply()) return false;
        if (result.resultType === 'reset') {
            this.#workspacePath = null;
            this.#displayPath = this.getCurrentWorkspacePath();
            return true;
        }
        const selected = resolveWorkspaceSelection(result);
        if (selected === undefined) return false;
        this.#workspacePath = selected;
        this.#displayPath = resolveWorkspaceDisplayPath(selected, this.getCurrentWorkspacePath());
        return true;
    }
}

export { WorkspacePathDraft, resolveWorkspaceDisplayPath, resolveWorkspaceSelection };
export type { WorkspacePathPickerStrings };
