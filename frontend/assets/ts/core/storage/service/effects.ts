/* SoAI - Shared storage service effects [frontend/assets/ts/core/storage/service/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { getBody, getDocumentElement } from '@core/environment/public.ts';
import { applyHeaderStatsLayout } from '@core/headerStatsLayout.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';

interface StorageUiEffects {
    bodyClass: (className: string, enabled: boolean) => void;
    setGlassDisabled: (disabled: boolean) => void;
    setAttr: (name: string, value: string) => void;
    reapplyHeaderStats: () => void;
}

const createStorageEffects = (): StorageUiEffects => {
    const bodyClass = (className: string, enabled: boolean): void => {
        getBody().classList.toggle(className, !!enabled);
    };

    const setGlassDisabled = (disabled: boolean): void => {
        bodyClass('glass-disabled', disabled);
        getDocumentElement().classList.toggle('glass-disabled', disabled);
    };

    const setAttr = (name: string, value: string): void => {
        getDocumentElement().setAttribute(name, value);
    };

    const reapplyHeaderStats = (): void => {
        try {
            const elements = dom.resolveAll('.ui-page-header-stats');
            for (const element of elements) {
                if (!(element instanceof HTMLElement)) {
                    continue;
                }
                applyHeaderStatsLayout(element);
            }
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.warn('StorageManager', 'Stats layout failed', runtimeError);
        }
    };

    return {
        bodyClass,
        setGlassDisabled,
        setAttr,
        reapplyHeaderStats
    };
};

export { createStorageEffects };
export type { StorageUiEffects };
