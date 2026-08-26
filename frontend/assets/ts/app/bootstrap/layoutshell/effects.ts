/* SoAI - Frontend application layout shell effects [frontend/assets/ts/app/bootstrap/layoutshell/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getComponentInitializeTimeoutMs } from '@app/bootstrap/layoutshell/constants.ts';
import { assertInitializableComponent, isBooleanResult } from '@app/bootstrap/layoutshell/guards.ts';
import type { ComponentDescriptor, ComponentInstance, InitializeOptions } from '@app/bootstrap/layoutshell/types.ts';
import { withTimeout } from '@core/primitives/withTimeout.ts';

const initializeLayoutShellComponent = async (
    descriptor: ComponentDescriptor,
    instance: ComponentInstance,
    options: InitializeOptions,
    hooks: {
        onInitializing: () => void;
        onInitialized: () => void;
        onReset: () => void;
        onActivate: () => void;
    }
): Promise<void> => {
    const initialize = instance.initialize;
    if (typeof initialize !== 'function') {
        if (descriptor.required) {
            throw new Error(`Layout shell component ${descriptor.key} does not expose initialize()`);
        }
        hooks.onReset();
        return;
    }
    hooks.onInitializing();
    assertInitializableComponent(descriptor, instance);
    const task = Promise.resolve(instance.initialize(options));
    const result = await withTimeout(task, { timeoutMs: getComponentInitializeTimeoutMs(), timeoutMessage: `Component ${descriptor.key} init timeout` });
    if (isBooleanResult(result) && result === false) {
        throw new Error(`Layout shell component ${descriptor.key} initialize() returned false`);
    }
    hooks.onActivate();
    hooks.onInitialized();
};

export { initializeLayoutShellComponent };
