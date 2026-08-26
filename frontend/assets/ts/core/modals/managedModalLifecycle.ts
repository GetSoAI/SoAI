/* SoAI - Shared modals managed modal lifecycle [frontend/assets/ts/core/modals/managedModalLifecycle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { runCleanupStepCollectingFailure, throwCollectedCleanupFailures } from '@core/lifecycle/cleanup.ts';
import type { ManagedModalLifecycle } from '@core/modals/types.ts';

interface ManagedModalCloseBinding {
    modalId: string;
    onModalClosed: () => void;
}

type ManagedModalDisposable = Pick<ManagedModalLifecycle, 'disposeForPageDestroy'>;

interface ManagedModalLifecycleBindOptions {
    signal: AbortSignal;
    resolveModalElement: (modalId: string) => HTMLElement;
    bindings: readonly ManagedModalCloseBinding[];
}

const createManagedModalCloseBinding = (modalId: string, lifecycle: ManagedModalLifecycle): ManagedModalCloseBinding => ({
    modalId,
    onModalClosed: () => lifecycle.onModalClosed()
});

const bindManagedModalLifecycleEvents = (options: ManagedModalLifecycleBindOptions): void => {
    const resolvedBindings = options.bindings.map((binding) => ({
        binding,
        element: options.resolveModalElement(binding.modalId)
    }));
    resolvedBindings.forEach(({ binding, element }) => {
        element.addEventListener('core.modal.close', binding.onModalClosed, { signal: options.signal });
    });
};

const disposeManagedModalLifecycles = (lifecycles: readonly ManagedModalDisposable[]): void => {
    const failures: Error[] = [];
    lifecycles.forEach((lifecycle) => {
        runCleanupStepCollectingFailure(() => lifecycle.disposeForPageDestroy(), failures);
    });
    throwCollectedCleanupFailures(failures);
};

export { bindManagedModalLifecycleEvents, createManagedModalCloseBinding, disposeManagedModalLifecycles };
