/* SoAI - Shared frontend SoAI OS capabilities runtime [frontend/assets/ts/core/soaiOsCapabilitiesRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction, isObject } from '@core/typeGuards.ts';
import type { SoaiOsCapabilitiesService } from '@core/soaiOsAccess.ts';
import { resolveOptionalKernelService, resolveKernelService } from '@core/runtime/runtimeContext.ts';

const isSoaiOsCapabilitiesContract = <T>(value: T): value is T & SoaiOsCapabilitiesService => {
    if (!isObject(value)) {
        return false;
    }
    return !('initialize' in value) || value.initialize === undefined || isFunction(value.initialize);
};

const SOAI_OS_CAPABILITIES_SERVICE_ID = 'core.soaiOsCapabilities';

const requireSoaiOsCapabilities = (): SoaiOsCapabilitiesService => {
    const candidate = resolveKernelService(SOAI_OS_CAPABILITIES_SERVICE_ID);
    if (!isSoaiOsCapabilitiesContract(candidate)) {
        throw new Error(`${SOAI_OS_CAPABILITIES_SERVICE_ID} is not configured`);
    }
    return candidate;
};

const getSoaiOsCapabilities = (): SoaiOsCapabilitiesService | null => {
    const candidate = resolveOptionalKernelService(SOAI_OS_CAPABILITIES_SERVICE_ID);
    return isSoaiOsCapabilitiesContract(candidate) ? candidate : null;
};

export { getSoaiOsCapabilities, requireSoaiOsCapabilities };
