/* SoAI - Frontend application layout shell constants [frontend/assets/ts/app/bootstrap/layoutshell/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getCoreTimeout } from '@core/runtime/runtimeContext.ts';

let componentInitializeTimeoutCache: number | null = null;

const getComponentInitializeTimeoutMs = (): number => {
    if (componentInitializeTimeoutCache !== null) {
        return componentInitializeTimeoutCache;
    }
    const value = getCoreTimeout('CORE_MODULES');
    if (typeof value !== 'number' || !Number.isFinite(value)) {
        throw new Error('CORE_MODULES timeout must be a finite number');
    }
    if (value <= 0) {
        throw new Error('CORE_MODULES timeout must be positive');
    }
    componentInitializeTimeoutCache = value;
    return value;
};

export { getComponentInitializeTimeoutMs };
