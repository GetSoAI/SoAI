/* SoAI - Shared DOM effects [frontend/assets/ts/core/dom/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DOMContext, DOMTarget, DOMUpdate } from '@core/dom/types.ts';
import { isDocumentFragment } from '@core/dom/domEnvironment.ts';

import type { DOMUpdateServiceRuntime } from '@core/dom/internalContracts.ts';
import { applyDOMUpdate, resolveDOMElement } from '@core/dom/adapters/public.ts';

const queueDOMUpdate = (runtime: DOMUpdateServiceRuntime, target: DOMTarget, context: DOMContext, update: DOMUpdate): void => {
    const element = resolveDOMElement(runtime, target, context);
    if (!element) return;

    const isDomNode = runtime.dependencies.isNode(element);
    const isDetached = isDomNode && element.isConnected === false;
    const shouldBatch = runtime.batchingEnabled && isDomNode && !isDocumentFragment(element) && !isDetached;

    if (!shouldBatch) {
        applyDOMUpdate(runtime, element, [update]);
        runtime.performanceMetrics.totalUpdates += 1;
        return;
    }

    const existing = runtime.pendingUpdates.get(element) ?? {
        element,
        updates: []
    };
    existing.updates.push(update);
    runtime.pendingUpdates.set(element, existing);

    if (!runtime.batchTimer) {
        const requestAnimationFrame = runtime.dependencies.getRequestAnimationFrame();
        runtime.batchTimer = requestAnimationFrame(() => {
            runtime.batchTimer = null;
            processPendingUpdates(runtime);
        });
    }
};

const processPendingUpdates = (runtime: DOMUpdateServiceRuntime): void => {
    if (runtime.pendingUpdates.size === 0) return;

    const batchSize = runtime.pendingUpdates.size;
    runtime.performanceMetrics.batchedUpdates += 1;
    runtime.performanceMetrics.averageBatchSize = (runtime.performanceMetrics.averageBatchSize * (runtime.performanceMetrics.batchedUpdates - 1) + batchSize) / runtime.performanceMetrics.batchedUpdates;

    for (const { element, updates } of runtime.pendingUpdates.values()) {
        applyDOMUpdate(runtime, element, updates);
        runtime.performanceMetrics.totalUpdates += updates.length;
    }

    runtime.pendingUpdates.clear();
};

const flushDOMUpdates = (runtime: DOMUpdateServiceRuntime): void => {
    if (runtime.batchTimer) {
        const cancelAnimationFrame = runtime.dependencies.getCancelAnimationFrame();
        cancelAnimationFrame(runtime.batchTimer);
        runtime.batchTimer = null;
    }
    processPendingUpdates(runtime);
};

export { queueDOMUpdate, flushDOMUpdates };
