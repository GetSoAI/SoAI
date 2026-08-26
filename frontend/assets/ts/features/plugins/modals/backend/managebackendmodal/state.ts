/* SoAI - Plugins feature manage backend modal state [frontend/assets/ts/features/plugins/modals/backend/managebackendmodal/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ManageState } from '@features/plugins/modals/backend/managebackendmodal/types.ts';

const createManageInitialState = (): ManageState => {
    return { currentPlugin: null, updateInfo: null, backendVariantsReady: false };
};

const clearManageState = (state: ManageState): void => {
    state.currentPlugin = null;
    state.updateInfo = null;
    state.backendVariantsReady = false;
};

export { clearManageState, createManageInitialState };
