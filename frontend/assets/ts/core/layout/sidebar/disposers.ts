/* SoAI - Shared layout disposers [frontend/assets/ts/core/layout/sidebar/disposers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { isFunction } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';

type SidebarDisposerCandidate = (() => void) | null | undefined;

const addSidebarDisposer = (set: Set<() => void>, functionValue: SidebarDisposerCandidate, type: string): (() => void) => {
    if (!isFunction(functionValue)) {
        return () => {};
    }

    let active = true;
    const disposer = functionValue;
    const wrapped = (): void => {
        if (!active) {
            return;
        }
        active = false;
        set.delete(wrapped);
        try {
            disposer();
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.debug('Sidebar', `${type} disposer failed`, runtimeError);
        }
    };

    set.add(wrapped);
    return wrapped;
};

const flushSidebarDisposers = (set: Set<() => void>, type: string): void => {
    Array.from(set).forEach((disposer) => {
        try {
            disposer();
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.debug('Sidebar', `${type} cleanup failed`, runtimeError);
        }
    });
    set.clear();
};

export { addSidebarDisposer, flushSidebarDisposers };
export type { SidebarDisposerCandidate };
