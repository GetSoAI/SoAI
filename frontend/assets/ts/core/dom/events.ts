/* SoAI - Shared DOM events [frontend/assets/ts/core/dom/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DOMUpdateServiceRuntime } from '@core/dom/internalContracts.ts';

const cleanupDOMListeners = (runtime: DOMUpdateServiceRuntime, element: Element): void => {
    const listeners = runtime.listenerRegistry.get(element);
    if (!listeners) return;
    for (const entry of listeners) {
        element.removeEventListener(entry.event, entry.handler);
    }
    runtime.listenerRegistry.delete(element);
};

export { cleanupDOMListeners };
