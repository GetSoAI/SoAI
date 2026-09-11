/* SoAI - Workspace browser access policy [frontend/assets/ts/core/fileexplorerbrowser/workspaceBrowserAccess.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { WebuiUser } from '@core/api/contracts/webuiUserContracts.ts';
import type { ReadOnlyFileBrowserApi } from '@core/fileexplorerbrowser/types.ts';

interface WorkspaceBrowserAccess {
    currentWorkspacePath: string;
    browserApi: ReadOnlyFileBrowserApi;
}

interface WorkspaceBrowserAccessApi {
    getCurrentUser(): Promise<WebuiUser>;
    scopedBrowserApi: ReadOnlyFileBrowserApi;
}

const resolveWorkspaceBrowserAccess = async (api: WorkspaceBrowserAccessApi): Promise<WorkspaceBrowserAccess> => {
    const user = await api.getCurrentUser();
    const currentWorkspacePath = user.workspacePathResolved.trim();
    if (!currentWorkspacePath) {
        throw new Error('Current workspace path is empty.');
    }
    return {
        currentWorkspacePath,
        browserApi: api.scopedBrowserApi
    };
};

export { resolveWorkspaceBrowserAccess };
export type { WorkspaceBrowserAccess, WorkspaceBrowserAccessApi };
