/* SoAI - Shared DOM internal contracts [frontend/assets/ts/core/dom/internalContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SecurityAPI } from '@core/security/public.ts';

import type { DOMContext, DOMPlainRecord, DOMRuntimeCandidate, DOMTarget, DOMUpdate, PerformanceMetrics } from '@core/dom/types.ts';

interface DomUpdateServiceDependencies {
    security: Pick<SecurityAPI, 'escapeHtml' | 'sanitizeHtml'>;
    errorHandler: { warn: (module: string, message: string, error?: Error) => void };
    ensureArray: <T>(value: T | T[]) => T[];
    toTrimmedString: <T>(value: T) => string;
    toString: <T>(value: T) => string;
    isPlainObject: (value: DOMRuntimeCandidate) => value is DOMPlainRecord;
    isNullOrUndefined: <T>(value: T) => boolean;
    isString: (value: DOMRuntimeCandidate) => value is string;
    isArray: <T>(value: T) => boolean;
    isElementNode: (value: DOMRuntimeCandidate) => value is Element;
    isNode: (value: DOMRuntimeCandidate) => value is Node;
    isHTMLElement: (value: DOMRuntimeCandidate) => value is HTMLElement;
    getDomDocument: () => Document;
    getRequestAnimationFrame: () => (callback: FrameRequestCallback) => number;
    getCancelAnimationFrame: () => (handle: number) => void;
    captureScrollState: (element: HTMLElement) => Array<{ element: HTMLElement; top: number; left: number }>;
    restoreScrollState: (state: Array<{ element: HTMLElement; top: number; left: number }>) => void;
    applyDynamicStyle: (element: HTMLElement | SVGElement, property: string, value: string | null) => void;
    resolve: (target: DOMTarget, context?: DOMContext) => Element | null;
}

interface ListenerRegistryEntry {
    event: string;
    handler: EventListener;
}

interface PendingUpdateEntry {
    element: Element | DocumentFragment;
    updates: DOMUpdate[];
}

interface DOMUpdateServiceRuntime {
    dependencies: DomUpdateServiceDependencies;
    pendingUpdates: Map<Element | DocumentFragment, PendingUpdateEntry>;
    batchTimer: number | null;
    batchingEnabled: boolean;
    performanceMetrics: PerformanceMetrics;
    listenerRegistry: WeakMap<Element, ListenerRegistryEntry[]>;
}

export type { DomUpdateServiceDependencies, ListenerRegistryEntry, PendingUpdateEntry, DOMUpdateServiceRuntime };
