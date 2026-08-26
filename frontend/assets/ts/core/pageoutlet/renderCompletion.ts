/* SoAI - Shared page outlet render completion [frontend/assets/ts/core/pageoutlet/renderCompletion.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { errorHandler } from '@core/errorHandler.ts';

interface PageOutletRenderCompletionContext {
    component: string;
    refresh: boolean;
    startedAt: number;
}

interface PageOutletRenderCompletionHost {
    emitEvent: (stage: string, payload?: Record<string, JsonValue>, severity?: string) => void;
}

const completePageOutletRender = (context: PageOutletRenderCompletionContext, host: PageOutletRenderCompletionHost): void => {
    const duration = performance.now() - context.startedAt;
    const payload = {
        component: context.component,
        refresh: context.refresh,
        durationMs: Number(duration.toFixed(2))
    };
    host.emitEvent('component:load:ready', payload);
    errorHandler.info('PageOutlet', 'Component load complete', payload);
};

export { completePageOutletRender };
