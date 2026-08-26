/* SoAI - Shared page outlet contracts [frontend/assets/ts/core/pageoutlet/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PageInstance, PageRegistry } from '@core/pagehost/types.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

interface PageOutletRenderOptions {
    component?: string | undefined;
    parameters?: JsonObject | undefined;
    refresh?: boolean | undefined;
    beforePrepare?: (() => void | Promise<void>) | Promise<void> | null | undefined;
    beforeCommit?: (() => void | Promise<void>) | Promise<void> | null | undefined;
    commitNavigation?: (() => void) | undefined;
    readyTimeoutMs?: number | undefined;
    signal?: AbortSignal | undefined;
}

interface PageOutletDestroyOptions {
    force?: boolean | undefined;
}

type PageOutletEventEmitter = (stage: string, payload?: Record<string, JsonValue | null | undefined>, severity?: string) => void;

type PageOutletRetryHandler = () => void;

interface TimeoutError extends Error {
    stage?: string | undefined;
    component?: string | undefined;
    timeoutMs?: number | undefined;
}

interface PageHostInstance {
    prepare: (component: string, parameters: JsonObject) => Promise<PageInstance | null>;
    commitPrepared: () => Promise<PageInstance | null>;
    cancelPrepared: (reason?: string) => void;
    cancelCurrent: (expectedInstance: PageInstance, reason?: string) => boolean;
    whenReady: (options?: { waitForData?: boolean; waitForReveal?: boolean }) => Promise<void>;
    allowReveal: () => void;
    destroyCurrent: (options?: { force?: boolean; reason?: string }) => Promise<void>;
    getCurrent: () => { name: string; instance: PageInstance } | null;
}

interface PageOutletOverlayElements {
    overlay: HTMLElement;
    overlayLabel: HTMLElement;
    overlayDetail: HTMLElement;
    overlayAction: HTMLButtonElement;
}

interface PageOutletStateOptions {
    label?: string | null;
    detail?: string | null;
    delayed?: boolean | undefined;
}

interface PageOutletErrorState {
    label: string;
    detail: string | null;
}

interface PageOutletConstructorOptions {
    emitEvent?: PageOutletEventEmitter | null | undefined;
    onPreservedPageFailure?: (() => void) | null | undefined;
    onRetry?: PageOutletRetryHandler | null | undefined;
    pageRegistry?: PageRegistry | null | undefined;
}

export type { PageHostInstance, PageOutletConstructorOptions, PageOutletDestroyOptions, PageOutletErrorState, PageOutletEventEmitter, PageOutletOverlayElements, PageOutletRenderOptions, PageOutletRetryHandler, PageOutletStateOptions, TimeoutError };
