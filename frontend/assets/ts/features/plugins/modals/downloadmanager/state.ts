/* SoAI - Plugins feature download manager state [frontend/assets/ts/features/plugins/modals/downloadmanager/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ManualPluginState } from '@features/plugins/modals/downloadmanager/contracts.ts';

const createManualPluginState = (): ManualPluginState => {
    return {
        loading: false,
        loaded: false,
        promise: null,
        pluginsPath: '',
        resolvedPath: '',
        error: null
    };
};

export { createManualPluginState };
