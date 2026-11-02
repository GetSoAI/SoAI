/* SoAI - Shared modals contracts [frontend/assets/ts/core/modals/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PresentationOwner } from '@core/routing/router/types.ts';

export type ModalUserCloseReason = 'escape' | 'overlay' | 'trigger';

export interface ModalBeforeCloseDetail {
    modalId: string;
    reason: ModalUserCloseReason;
}

export interface ModalCreationOptions {
    force?: boolean | undefined;
    layoutOverride?: ModalLayoutPreset | undefined;
}

export interface ModalOpenOptions extends ModalCreationOptions {
    readonly owner: PresentationOwner;
}

export interface ModalOwnership {
    readonly modalId: string;
    readonly owner: PresentationOwner;
    readonly generation: symbol;
    readonly signal: AbortSignal;
    readonly completion: Promise<ModalReleaseOutcome>;
}

export type ModalReleaseOutcome = { type: 'released' } | { type: 'failed'; error: Error };

export interface ModalCloseOptions {
    replacementFocusTarget?: HTMLElement | undefined;
    force?: boolean | undefined;
    restoreFocus?: boolean | undefined;
    reason?: string | undefined;
}

export type ModalLayoutPreset = 'md' | 'lg' | 'xl';

export interface ModalRegisterOptions {
    presentation?: 'window' | 'viewport';
    layout: ModalLayoutPreset;
    initialFocusSelector: string;
    resizable?: boolean | undefined;
    allowFullscreen?: boolean | undefined;
    onOpen?: ((modal: Element, options: ModalOpenOptions) => void) | null | undefined;
    onClose?: ((modal: Element, options: ModalCloseOptions) => void) | null | undefined;
}

export interface ModalConfig {
    presentation: 'window' | 'viewport';
    closeOnEsc: boolean;
    closeOnOverlay: boolean;
    restoreFocus: boolean;
    resizable: boolean;
    dynamic: boolean;
    size: ModalLayoutPreset;
    initialFocusSelector: string;
    defaultWidth: number | null;
    defaultHeight: number | null;
    minWidth: number;
    minHeight: number;
    maxWidth: number | null;
    maxHeight: number | null;
    onOpen: ((modal: Element, options: ModalOpenOptions) => void) | null;
    onClose: ((modal: Element, options: ModalCloseOptions) => void) | null;
    allowFullscreen: boolean;
}

export interface Position {
    x: number;
    y: number;
}

export interface Size {
    width: number;
    height: number;
}

export interface SavedModalState {
    size?: Size | undefined;
}

export interface ModalHandle {
    open: <TOptions extends ModalOpenOptions>(options: TOptions) => boolean;
    close: (options?: ModalCloseOptions | undefined) => boolean;
    toggle: (options: ModalOpenOptions, force?: boolean | null | undefined) => boolean;
    isOpen: () => boolean;
}

export interface ManagedModalLifecycle {
    onModalClosed(): void;
    disposeForPageDestroy(): void;
}
