/* SoAI - Settings page workspace path picker modal [frontend/assets/ts/pages/settings/controllers/usersmanager/workspacePathPickerModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { showFolderPickerModal } from '@core/fileexplorerbrowser/folderPickerModal.ts';
import { buildFolderPickerLabels } from '@core/fileexplorerbrowser/folderPickerLabels.ts';
import { isAbsoluteOsPath } from '@core/fileexplorerbrowser/paths.ts';
import type { ReadOnlyFileBrowserApi } from '@core/fileexplorerbrowser/types.ts';
import { i18n } from '@core/i18n/index.ts';
import type { WebuiUser } from '@core/api/contracts/webuiUserContracts.ts';
import type { UsersManagerApiHost } from '@pages/settings/controllers/usersmanager/types.ts';

const openUserWorkspacePathPicker = async (host: UsersManagerApiHost, user: WebuiUser): Promise<string | null | undefined> => {
    const defaultFolder = user.defaultWorkspacePath;
    const fileBrowserApi: ReadOnlyFileBrowserApi = {
        list: (options: Parameters<UsersManagerApiHost['listWorkspaceBrowser']>[0]) => host.listWorkspaceBrowser(options),
        search: (options: Parameters<UsersManagerApiHost['searchWorkspaceBrowser']>[0]) => host.searchWorkspaceBrowser(options)
    };
    const initialPath = user.workspacePathResolved.trim();
    const initialPathIsAbsolute = isAbsoluteOsPath(initialPath);
    const baseOptions = {
        api: fileBrowserApi,
        title: i18n.t('settings.users.changeWorkspacePathModal.title'),
        message: i18n.t('settings.users.changeWorkspacePathModal.message', { username: user.username, defaultFolder }),
        labels: buildFolderPickerLabels({
            chooseCurrent: i18n.t('common.save'),
            reset: i18n.t('settings.users.changeWorkspacePathModal.resetButton')
        }),
        allowManualPathEntry: true,
        allowManualAbsoluteSelectionOutsideRoot: true,
        ...(initialPath && initialPathIsAbsolute ? { initialAbsolutePathToBrowse: initialPath } : {}),
        ...(initialPath && !initialPathIsAbsolute ? { initialVirtualPath: initialPath } : {})
    } satisfies Parameters<typeof showFolderPickerModal>[0];
    const pickerResult = await showFolderPickerModal(baseOptions);
    if (pickerResult === null) {
        return undefined;
    }
    if (pickerResult.resultType === 'reset') {
        return null;
    }
    if (pickerResult.resultType === 'selected') {
        return pickerResult.absolutePath ?? pickerResult.virtualPath;
    }
    return null;
};

export { openUserWorkspacePathPicker };
