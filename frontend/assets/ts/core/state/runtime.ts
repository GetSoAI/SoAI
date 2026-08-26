/* SoAI - Shared state runtime [frontend/assets/ts/core/state/runtime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveOptionalKernelService, resolveKernelService } from '@core/runtime/runtimeContext.ts';
import { StateManager } from '@core/state/StateManager.ts';

const STATE_SERVICE_ID = 'core.state';

const requireStateManager = (): StateManager => {
    const candidate = resolveKernelService(STATE_SERVICE_ID);
    if (!(candidate instanceof StateManager)) {
        throw new Error(`${STATE_SERVICE_ID} is not registered`);
    }
    return candidate;
};

const getStateManager = (): StateManager | null => {
    const candidate = resolveOptionalKernelService(STATE_SERVICE_ID);
    return candidate instanceof StateManager ? candidate : null;
};

export { getStateManager, requireStateManager };
