/* SoAI - Shared modals contracts [frontend/assets/ts/core/modals/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

export type ModalUserCloseReason = 'escape' | 'overlay' | 'trigger';

export interface ModalBeforeCloseDetail {
    modalId: string;
    reason: ModalUserCloseReason;
}

export interface ModalOpenOptions {
    force?: boolean | undefined;
    layoutOverride?: ModalLayoutPreset | undefined;
}

export interface ModalCloseOptions {
    force?: boolean | undefined;
    restoreFocus?: boolean | undefined;
    reason?: string | undefined;
}

export type ModalLayoutPreset = 'md' | 'lg' | 'xl';

export interface ModalRegisterOptions {
    layout: ModalLayoutPreset;
    initialFocusSelector: string;
    resizable?: boolean | undefined;
    allowFullscreen?: boolean | undefined;
    onOpen?: ((modal: Element, options: ModalOpenOptions) => void) | null | undefined;
    onClose?: ((modal: Element, options: ModalCloseOptions) => void) | null | undefined;
}

export interface ModalConfig {
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
    open: <TOptions extends ModalOpenOptions>(options?: TOptions | undefined) => boolean;
    close: (options?: ModalCloseOptions | undefined) => boolean;
    toggle: (force?: boolean | null | undefined) => boolean;
    isOpen: () => boolean;
}

export interface ManagedModalLifecycle {
    onModalClosed(): void;
    disposeForPageDestroy(): void;
}
