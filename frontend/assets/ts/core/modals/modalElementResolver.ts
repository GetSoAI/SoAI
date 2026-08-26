/* SoAI - Standardized modal-scoped ElementResolver helper [frontend/assets/ts/core/modals/modalElementResolver.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ElementResolver } from '@core/dom/typedElements.ts';
import { createElementResolver } from '@core/dom/elementResolver.ts';

const createModalElementResolver = (modal: HTMLElement, labelPrefix: string): ElementResolver => {
    if (!(modal instanceof HTMLElement)) {
        throw new Error('createModalElementResolver requires a modal HTMLElement');
    }
    const prefix = String(labelPrefix || '').trim();
    if (!prefix) {
        throw new Error('createModalElementResolver requires a non-empty labelPrefix');
    }
    return createElementResolver(modal, prefix);
};

export { createModalElementResolver };
