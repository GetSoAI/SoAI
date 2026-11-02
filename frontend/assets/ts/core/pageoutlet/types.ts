/* SoAI - Shared page outlet contracts [frontend/assets/ts/core/pageoutlet/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PageHostCancellation, PageHostCommitOptions, PageHostPrepareOptions, PageHostOwnership, PageInstance, PageRegistry } from '@core/pagehost/types.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { PageMountScope } from '@core/routing/router/types.ts';

interface PageOutletRenderOptions {
    createMountScope: PageHostPrepareOptions['createMountScope'];
    component?: string | undefined;
    parameters?: JsonObject | undefined;
    refresh?: boolean | undefined;
    beforePrepare?: (() => void | Promise<void>) | Promise<void> | null | undefined;
    beforeCommit?: (() => void | Promise<void>) | Promise<void> | null | undefined;
    commitNavigation?: (() => void) | undefined;
    mountPublication?: PageHostCommitOptions['mountPublication'];
    afterCommit?: PageHostCommitOptions['afterCommit'];
    finalAdmission?: (() => void) | undefined;
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
    captureCancellation: (reason: string, scope?: 'all' | 'prepared') => PageHostCancellation;
    getOwnership: () => PageHostOwnership;
    getCurrentMountScope: () => PageMountScope | null;
    prepare: (component: string, parameters: JsonObject, options: PageHostPrepareOptions) => Promise<PageInstance | null>;
    commitPrepared: (options?: PageHostCommitOptions) => Promise<PageInstance | null>;
    cancelPrepared: (reason?: string) => void;
    cancelCurrent: (expectedInstance: PageInstance, reason?: string) => boolean;
    whenReady: (options?: { waitForData?: boolean; waitForReveal?: boolean }) => Promise<void>;
    allowReveal: () => void;
    destroyCurrent: (options?: { expectedInstance?: PageInstance; force?: boolean; reason?: string }) => Promise<void>;
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
    onStateChanged?: (() => void) | undefined;
    spinnerWorkerUrl?: string | undefined;
    emitEvent?: PageOutletEventEmitter | null | undefined;
    onPreservedPageFailure?: ((error: Error) => void) | null | undefined;
    onRetry?: PageOutletRetryHandler | null | undefined;
    pageRegistry?: PageRegistry | null | undefined;
}

export type { PageHostInstance, PageOutletConstructorOptions, PageOutletDestroyOptions, PageOutletErrorState, PageOutletEventEmitter, PageOutletOverlayElements, PageOutletRenderOptions, PageOutletRetryHandler, PageOutletStateOptions, TimeoutError };

interface PageOutletService {
    setContainer: (container: HTMLElement | string) => PageOutletService;
    getContainer: () => HTMLElement;
    getPageHost: () => PageHostInstance;
    peekPageHost: () => PageHostInstance | null;
    destroyCurrent: (options?: { force?: boolean }) => Promise<void>;
    whenReleased: () => Promise<void>;
    destroy?: () => Promise<void>;
    render: (options: PageOutletRenderOptions & { component: string; parameters: JsonObject }) => Promise<{ name: string; instance: PageInstance } | null>;
    cancelActive: (reason?: string) => void;
    waitForCommit: () => Promise<void>;
    setSkeleton: (route: string) => void;
    getState?: (() => string) | undefined;
}

export type { PageOutletService };
