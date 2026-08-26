/* SoAI - Frontend application layout shell validation [frontend/assets/ts/app/bootstrap/layoutshell/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction, isInstanceOf, isObject } from '@core/typeGuards.ts';
import type { ComponentDescriptor, ComponentInstance, InitializeOptions, LayoutShellDependencies } from '@app/bootstrap/layoutshell/types.ts';

const isBooleanResult = (value: boolean | null | undefined | void): value is boolean => typeof value === 'boolean';

function assertInitializableComponent(
    descriptor: ComponentDescriptor,
    instance: ComponentInstance
): asserts instance is ComponentInstance & {
    initialize: (options?: InitializeOptions) => Promise<void | boolean> | void | boolean;
} {
    if (!isFunction(instance.initialize)) {
        throw new Error(`Layout shell component ${descriptor.key} does not expose initialize()`);
    }
}

function assertDestroyableComponent(
    descriptor: ComponentDescriptor,
    instance: ComponentInstance
): asserts instance is ComponentInstance & {
    destroy: () => Promise<void | boolean> | void | boolean;
} {
    if (!isFunction(instance.destroy)) {
        throw new Error(`Layout shell component ${descriptor.key} does not expose destroy`);
    }
}

const assertLayoutShellDependencies = (dependencies: LayoutShellDependencies): void => {
    if (!dependencies || !isObject(dependencies)) {
        throw new Error('LayoutShell requires deps');
    }
    if (!isObject(dependencies.mainStatusMonitor)) {
        throw new Error('LayoutShell requires mainStatusMonitor');
    }
    if (!dependencies.componentRegistry || !isObject(dependencies.componentRegistry)) {
        throw new Error('LayoutShell requires a component registry');
    }
    if (!isInstanceOf(dependencies.componentRegistry.components, Map)) {
        throw new Error('LayoutShell requires a component registry map');
    }
    if (!isFunction(dependencies.componentRegistry.register)) {
        throw new Error('LayoutShell requires a component registry register method');
    }
    if (!isInstanceOf(dependencies.componentLookup, Map)) {
        throw new Error('LayoutShell requires a component lookup map');
    }
};

export { assertDestroyableComponent, assertInitializableComponent, assertLayoutShellDependencies, isBooleanResult };
