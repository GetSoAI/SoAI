/* SoAI - Shared page outlet render failure [frontend/assets/ts/core/pageoutlet/renderFailure.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { claimErrorReporting } from '@core/errors/reportingOwnership.ts';

interface PageOutletRenderFailureContext {
    component: string;
    refresh: boolean;
    startedAt: number;
    error: Error;
}

interface PageOutletRenderFailureHost {
    applyErrorState: (error: Error) => void;
    emitEvent: (stage: string, payload?: Record<string, JsonValue>, severity?: string) => void;
}

const reportPageOutletRenderFailure = (context: PageOutletRenderFailureContext, host: PageOutletRenderFailureHost): void => {
    const duration = performance.now() - context.startedAt;
    const runtimeError = context.error;
    const payload = {
        component: context.component,
        refresh: context.refresh,
        durationMs: Number(duration.toFixed(2)),
        message: runtimeError.message || null
    };
    host.applyErrorState(runtimeError);
    if (claimErrorReporting(runtimeError)) {
        host.emitEvent('component:load:error', payload, 'error');
    }
};

export { reportPageOutletRenderFailure };
