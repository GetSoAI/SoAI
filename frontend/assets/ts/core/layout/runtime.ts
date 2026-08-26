/* SoAI - Shared layout runtime [frontend/assets/ts/core/layout/runtime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction, isObject } from '@core/typeGuards.ts';
import { resolveOptionalKernelService, resolveKernelService } from '@core/runtime/runtimeContext.ts';

interface HeaderDropdownContract {
    closeDropdowns: () => void;
}

const isHeaderDropdownContract = <T>(value: T): value is T & HeaderDropdownContract => {
    if (!isObject(value)) {
        return false;
    }
    return 'closeDropdowns' in value && isFunction(value.closeDropdowns);
};

const getLayoutHeaderOptional = (): HeaderDropdownContract | null => {
    const candidate = resolveOptionalKernelService('core.layout.header');
    return isHeaderDropdownContract(candidate) ? candidate : null;
};

const requireLayoutHeader = (): HeaderDropdownContract => {
    const candidate = resolveKernelService('core.layout.header');
    if (!isHeaderDropdownContract(candidate)) {
        throw new Error('core.layout.header is not configured');
    }
    return candidate;
};

export { getLayoutHeaderOptional, requireLayoutHeader };
