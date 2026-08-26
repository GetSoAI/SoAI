/* SoAI - Frontend tooltip service registry [frontend/assets/ts/core/ui/tooltips/tooltipServiceRegistry.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasFunctionProperties, isObject } from '@core/typeGuards.ts';
import type { TooltipService } from '@core/ui/tooltips/service.ts';
import { resolveOptionalKernelService, resolveKernelService } from '@core/runtime/runtimeContext.ts';

const isTooltipService = <T>(value: T): value is T & TooltipService => {
    if (!isObject(value)) {
        return false;
    }
    return hasFunctionProperties(value, ['initialize', 'teardown']);
};

const resetTooltipService = (): void => {
    const candidate = resolveOptionalKernelService('core.tooltipService');
    if (isTooltipService(candidate)) {
        candidate.teardown();
    }
};

const getTooltipService = (): TooltipService => {
    const candidate = resolveKernelService('core.tooltipService');
    if (!isTooltipService(candidate)) {
        throw new Error('core.tooltipService is not registered');
    }
    return candidate;
};

export { getTooltipService, resetTooltipService };
export type { TooltipService };
