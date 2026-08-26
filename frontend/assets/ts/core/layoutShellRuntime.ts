/* SoAI - Shared frontend layout shell runtime [frontend/assets/ts/core/layoutShellRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction, isObject } from '@core/typeGuards.ts';
import { resolveOptionalKernelService, resolveKernelService } from '@core/runtime/runtimeContext.ts';

interface LayoutShellContract {
    teardown: () => Promise<void>;
}

const isLayoutShellContract = <T>(value: T): value is T & LayoutShellContract => {
    if (!isObject(value)) {
        return false;
    }
    return 'teardown' in value && isFunction(value.teardown);
};

const LAYOUT_SHELL_SERVICE_ID = 'core.layoutShell';

const requireLayoutShell = (): LayoutShellContract => {
    const candidate = resolveKernelService(LAYOUT_SHELL_SERVICE_ID);
    if (!isLayoutShellContract(candidate)) {
        throw new Error(`${LAYOUT_SHELL_SERVICE_ID} is not configured`);
    }
    return candidate;
};

const getLayoutShellOptional = (): LayoutShellContract | null => {
    const candidate = resolveOptionalKernelService(LAYOUT_SHELL_SERVICE_ID);
    return isLayoutShellContract(candidate) ? candidate : null;
};

export { getLayoutShellOptional, requireLayoutShell };
