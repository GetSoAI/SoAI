/* SoAI - Shared page outlet render failure [frontend/assets/ts/core/pageoutlet/renderFailure.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { claimErrorReporting } from '@core/errors/reportingOwnership.ts';
import { PageContainerRollbackError } from '@core/pagehost/actions.ts';
import type { PageOutletStateOptions } from '@core/pageoutlet/types.ts';

class PageOutletCleanupError extends AggregateError {
    readonly code = 'page_resource_release_unconfirmed';

    constructor(failure: Error, cleanupFailure: Error, message = failure.message) {
        super([failure, cleanupFailure], message);
    }
}

interface PageOutletRenderFailureContext {
    component: string;
    refresh: boolean;
    startedAt: number;
    error: Error;
}

interface PageOutletRenderFailureHost {
    overlay: {
        setState(state: string, options?: PageOutletStateOptions): void;
        applyErrorState(error: Error): void;
    };
    preserveCurrentPage: boolean;
    onPreservedPageFailure: ((error: Error) => void) | null;
    emitEvent?: ((stage: string, payload?: Record<string, JsonValue>, severity?: string) => void) | undefined;
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
    if (host.preserveCurrentPage && !(runtimeError instanceof PageContainerRollbackError)) {
        host.overlay.setState('ready');
        host.onPreservedPageFailure?.(runtimeError);
    } else {
        host.overlay.applyErrorState(runtimeError);
    }
    if (host.emitEvent && claimErrorReporting(runtimeError)) {
        host.emitEvent('component:load:error', payload, 'error');
    }
};

export { PageOutletCleanupError, reportPageOutletRenderFailure };
