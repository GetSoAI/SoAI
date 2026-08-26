/* SoAI - Frontend application layout shell contracts [frontend/assets/ts/app/bootstrap/layoutshell/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ComponentRegistry } from '@core/componentsupport/public.ts';

interface ComponentDescriptor {
    key: string;
    identifier: string | null;
    registryNames: readonly string[];
    registryOptions?: Record<string, JsonValue> | undefined;
    required: boolean;
}

interface InitializeOptions {
    force?: boolean | undefined;
}

interface ComponentInstance {
    initialize?: ((options?: InitializeOptions) => Promise<void | boolean> | void | boolean) | undefined;
    destroy?: (() => Promise<void | boolean> | void | boolean) | undefined;
    disconnect?: (() => void) | undefined;
}

interface LayoutShellDependencies {
    mainStatusMonitor: ComponentInstance;
    componentRegistry: ComponentRegistry;
    componentLookup: Map<string, ComponentInstance>;
}

interface LayoutShellState {
    initialized: boolean;
    bootPromise: Promise<boolean> | null;
    active: Map<string, ComponentInstance>;
}

export type { ComponentDescriptor, ComponentInstance, InitializeOptions, LayoutShellDependencies, LayoutShellState };
