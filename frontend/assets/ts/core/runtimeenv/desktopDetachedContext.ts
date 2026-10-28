/* SoAI - Detached desktop navigation state and ownership [frontend/assets/ts/core/runtimeenv/desktopDetachedContext.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isDesktopLauncherHost, registerDesktopLauncherDetachedContextCapture, takeDesktopLauncherDetachedContext } from '@core/desktophost/desktopLauncher.ts';
import { getEventHub } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { parseDetachedContextPayload, serializeDetachedContext } from '@core/runtimeenv/mappers.ts';
import type { DetachedContext } from '@core/runtimeenv/internalContracts.ts';
import { createStorageTextAdapter } from '@core/storage/ttlStorageCache.ts';
import { parseRequiredJsonObjectText } from '@core/serialization/json.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { readRequiredPositiveSafeIntegerValue } from '@core/types/payloadNumberReaders.ts';

interface DesktopDetachedContext {
    context: DetachedContext;
    ownerUserId: number;
}

const storageKey = (windowId: string): string => `soai.desktop.detached.${windowId}`;

const readDesktopDetachedContext = (windowId: string, pageId: string | null): DesktopDetachedContext | null => {
    if (!isDesktopLauncherHost()) return null;
    let handoff = takeDesktopLauncherDetachedContext();
    if (handoff === null) {
        const stored = createStorageTextAdapter('sessionStorage').getItem(storageKey(windowId));
        if (stored === null) return null;
        handoff = parseRequiredJsonObjectText(stored, 'Stored detached context must be an object');
    }
    const context = parseDetachedContextPayload(handoff['context'] ?? null, { logDetachedWarning: (message) => errorHandler.warn('Detached', message) });
    const ownerUserId = readRequiredPositiveSafeIntegerValue(handoff['ownerUserId'], 'Detached owner');
    if (!context || context.windowId !== windowId || context.metadata.pageId !== pageId || Object.keys(context.state).length !== 0) throw new Error('Desktop detached context does not match this window');
    return { context, ownerUserId };
};

const registerDesktopDetachedContextCapture = (windowId: string, capture: () => DesktopDetachedContext | null): (() => void) => {
    if (!isDesktopLauncherHost()) return () => {};
    const snapshot = (): JsonObject | null => {
        const current = capture();
        return current ? { context: serializeDetachedContext(current.context), ownerUserId: current.ownerUserId } : null;
    };
    const releaseCapture = registerDesktopLauncherDetachedContextCapture(snapshot);
    const storage = createStorageTextAdapter('sessionStorage');
    const persist = (event: Event): void => {
        try {
            const context = snapshot();
            if (context !== null) storage.setItem(storageKey(windowId), JSON.stringify(context));
        } catch (error) {
            event.preventDefault();
            if (event instanceof BeforeUnloadEvent) event.returnValue = '';
            errorHandler.warn('Detached', 'Could not preserve detached navigation state', ensureError(error));
        }
    };
    getEventHub().addEventListener('beforeunload', persist);
    return () => {
        releaseCapture();
        getEventHub().removeEventListener('beforeunload', persist);
    };
};

export { readDesktopDetachedContext, registerDesktopDetachedContextCapture };
export type { DesktopDetachedContext };
