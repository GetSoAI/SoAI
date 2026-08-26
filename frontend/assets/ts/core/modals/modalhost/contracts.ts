/* SoAI - Shared frontend modal modalhost boundary contracts [frontend/assets/ts/core/modals/modalhost/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ModalRegistry } from '@core/modals/ModalRegistry.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import type { DragState, FullscreenState, ModalPageLockSnapshot, ModalStorageApi, ResizeState } from '@core/modals/modalhost/types.ts';
import type { ModalLayoutPreset } from '@core/modals/types.ts';

interface ModalHostState {
    readonly registry: ModalRegistry;
    readonly storage: ModalStorageApi;
    readonly resources: ResourceTracker;
    readonly resolveModalElement: (id: string) => HTMLElement | null;
    readonly ensureModalElement: (id: string) => HTMLElement;

    activeStack: string[];
    focusMemory: Map<string, Element>;
    dragState: Map<string, DragState>;
    resizeState: Map<string, ResizeState>;
    fullscreenState: Map<string, FullscreenState>;
    layoutOverrides: Map<string, ModalLayoutPreset>;
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

const createModalHostState = ({ storage, resolveModalElement, ensureModalElement }: { storage: ModalStorageApi; resolveModalElement: (id: string) => HTMLElement | null; ensureModalElement: (id: string) => HTMLElement }): ModalHostState => {
    return {
        registry: new ModalRegistry(),
        storage,
        resources: new ResourceTracker(),
        resolveModalElement,
        ensureModalElement,
        activeStack: [],
        focusMemory: new Map(),
        dragState: new Map(),
        resizeState: new Map(),
        fullscreenState: new Map(),
        layoutOverrides: new Map(),
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

export type { ModalHostState };
export { createModalHostState };
