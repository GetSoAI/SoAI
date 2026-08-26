/* SoAI - Shared pagehost contracts [frontend/assets/ts/core/pagehost/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ErrorHandler } from '@core/errorHandler.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

interface PageHostDomApi {
    resolve(selector: string): Element | null;
    setHTML(element: HTMLElement, html: TrustedHtml | string, options: { escape: boolean }): void;
}

interface PageMeta {
    name?: string;
}

interface PageInstance {
    container?: HTMLElement | null;
    abortController?: AbortController | null;
    initialize?(parameters: JsonObject): Promise<void> | void;
    pageLifecycle?: {
        whenReady(options?: { waitForData?: boolean; waitForReveal?: boolean }): Promise<void>;
        allowReveal(): void;
        deferActivation(): void;
        activate(): void;
    };
    hide?(): Promise<boolean | void> | boolean | void;
    cleanup?(): Promise<boolean | void> | boolean | void;
    destroy?(): Promise<boolean | void> | boolean | void;
    cancel?(reason: string): void;
    setContainer?(container: HTMLElement): void;
}

interface PageRegistry {
    create(name: string): PageInstance | null;
    getMeta(name: string): PageMeta | null;
}

interface CurrentPageState {
    name: string;
    instance: PageInstance;
    meta: PageMeta;
    token: symbol;
    container: HTMLElement;
    preparedPromise: Promise<void>;
    viewReadyPromise: Promise<void>;
    dataReadyPromise: Promise<void>;
    isPreparationComplete: boolean;
}

type PreparedPageState = CurrentPageState;

type CleanupMethodName = 'cleanup' | 'destroy';

type CleanupRunner = (instance: PageInstance, methods: readonly CleanupMethodName[]) => Promise<void>;

interface PageHostOptions {
    registry?: PageRegistry | null;
    container?: HTMLElement | string | null;
    domResolver?: () => PageHostDomApi | null;
    errorHandler?: ErrorHandler;
    cleanupRunner?: CleanupRunner;
}

interface WhenReadyOptions {
    waitForData?: boolean;
    waitForReveal?: boolean;
}

interface DestroyOptions {
    force?: boolean;
    reason?: string;
}

export type { CleanupMethodName, CleanupRunner, CurrentPageState, DestroyOptions, PageHostDomApi, PageHostOptions, PageInstance, PageMeta, PageRegistry, PreparedPageState, WhenReadyOptions };
