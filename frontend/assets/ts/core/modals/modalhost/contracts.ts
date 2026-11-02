/* SoAI - Shared frontend modal modalhost boundary contracts [frontend/assets/ts/core/modals/modalhost/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ModalRegistry } from '@core/modals/ModalRegistry.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import type { Cleanup } from '@core/lifecycle/cleanup.ts';
import type { Deferred } from '@core/runtime/deferred.ts';
import type { DragState, FullscreenState, ModalPageLockSnapshot, ModalStorageApi, ResizeState } from '@core/modals/modalhost/types.ts';
import type { ModalLayoutPreset, ModalOwnership, ModalReleaseOutcome } from '@core/modals/types.ts';

type ModalOwnershipLifetime = { controller: AbortController; completion: Deferred<ModalReleaseOutcome>; disposeObservation: (() => void) | null; disposeSession: Cleanup | null; cleanup: () => Promise<void> } & ({ type: 'acquiring' } | { type: 'active' } | { type: 'releasing' } | { type: 'failed'; error: Error });

interface ModalHostState {
    readonly registry: ModalRegistry;
    readonly storage: ModalStorageApi;
    readonly resources: ResourceTracker;
    readonly resolveModalElement: (id: string) => HTMLElement | null;
    readonly ensureModalElement: (id: string) => HTMLElement;

    activeStack: string[];
    ownership: Map<string, ModalOwnership>;
    ownershipLifetimes: Map<ModalOwnership, ModalOwnershipLifetime>;
    readonly onOwnershipRevoked: (ownership: ModalOwnership) => void;
    focusMemory: Map<string, Element>;
    viewportInertSnapshots: Map<HTMLElement, boolean>;
    viewportBodyObserver: MutationObserver | null;
    dragState: Map<string, DragState>;
    resizeState: Map<string, ResizeState>;
    fullscreenState: Map<string, FullscreenState>;
    fullscreenTransitions: WeakMap<HTMLElement, AbortController>;
    layoutOverrides: Map<string, ModalLayoutPreset>;
    desktopOpenHeights: Map<string, number>;
    dockHintElement: HTMLElement | null;
    dockHintVisible: boolean;
    dockHintVisibilityToken: number;

    pageLockSnapshot: ModalPageLockSnapshot | null;
    viewportRefreshScheduled: boolean;
    layoutGeneration: number;
    mobileBreakpoint: number;
    isMobileViewportState: boolean;
    previousMobileViewportState: boolean;

    initialized: boolean;
}

const createModalHostState = ({ storage, resolveModalElement, ensureModalElement, onOwnershipRevoked }: { storage: ModalStorageApi; resolveModalElement: (id: string) => HTMLElement | null; ensureModalElement: (id: string) => HTMLElement; onOwnershipRevoked: (ownership: ModalOwnership) => void }): ModalHostState => {
    return {
        registry: new ModalRegistry(),
        storage,
        resources: new ResourceTracker(),
        resolveModalElement,
        ensureModalElement,
        activeStack: [],
        ownership: new Map(),
        ownershipLifetimes: new Map(),
        onOwnershipRevoked,
        focusMemory: new Map(),
        viewportInertSnapshots: new Map(),
        viewportBodyObserver: null,
        dragState: new Map(),
        resizeState: new Map(),
        fullscreenState: new Map(),
        fullscreenTransitions: new WeakMap(),
        layoutOverrides: new Map(),
        desktopOpenHeights: new Map(),
        dockHintElement: null,
        dockHintVisible: false,
        dockHintVisibilityToken: 0,
        pageLockSnapshot: null,
        viewportRefreshScheduled: false,
        layoutGeneration: 0,
        mobileBreakpoint: 768,
        isMobileViewportState: false,
        previousMobileViewportState: false,
        initialized: false
    };
};

export type { ModalHostState, ModalOwnershipLifetime };
export { createModalHostState };
