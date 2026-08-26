/* SoAI - Shared resource tracker contracts [frontend/assets/ts/core/resourcetracker/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type EventHandler = (event: Event, target?: Element | null) => void;

interface EventListenerOptions {
    capture?: boolean;
    passive?: boolean;
    once?: boolean;
}

interface EventTargetContract {
    addEventListener: (event: string, handler: EventListener, options?: EventListenerOptions | boolean) => void;
    removeEventListener?: (event: string, handler: EventListener, options?: EventListenerOptions | boolean) => void;
}

interface EventListenerMetadata {
    element: EventTargetContract;
    event: string;
    handler: EventListener;
    options: EventListenerOptions | boolean;
    originalHandler?: EventHandler;
}

interface DisposableMetadata {
    disposable: DisposableResource;
    cleanup?: ((disposable: DisposableResource) => void | Promise<void>) | undefined;
}

interface ResourceSnapshot {
    eventListeners: number;
    timeouts: number;
    intervals: number;
    animationFrames: number;
    disposables: number;
}

interface Disposable {
    destroy?: () => void | Promise<void>;
    dispose?: () => void | Promise<void>;
    cleanup?: () => void | Promise<void>;
    close?: () => void | Promise<void>;
    abort?: () => void | Promise<void>;
    cancel?: () => void | Promise<void>;
    disconnect?: () => void | Promise<void>;
    stop?: () => void | Promise<void>;
    clear?: () => void | Promise<void>;
    unsubscribe?: () => void | Promise<void>;
    off?: () => void | Promise<void>;
}

type DisposableResource = Disposable | (() => void) | null | undefined;

type EventTargetInput = EventTargetContract | readonly EventTargetContract[] | Iterable<EventTargetContract> | null | undefined;

export type { Disposable, DisposableMetadata, DisposableResource, EventHandler, EventListenerMetadata, EventListenerOptions, EventTargetContract, EventTargetInput, ResourceSnapshot };
