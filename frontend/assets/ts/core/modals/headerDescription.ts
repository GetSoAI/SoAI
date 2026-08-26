/* SoAI - Modal header description state helpers [frontend/assets/ts/core/modals/headerDescription.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';

const setModalHeaderDescription = (modalRoot: HTMLElement, descriptionId: string, text: string | null): void => {
    let descriptionElement: HTMLElement | null = null;
    for (const candidate of dom.resolveAll('[id]', modalRoot)) {
        if (candidate instanceof HTMLElement && candidate.id === descriptionId) {
            descriptionElement = candidate;
            break;
        }
    }
    if (!(descriptionElement instanceof HTMLElement)) {
        throw new Error(`Modal header description element is missing: ${descriptionId}`);
    }
    const value = text?.trim() ?? '';
    descriptionElement.textContent = value;
    descriptionElement.classList.toggle('u-hidden', !value);
};

export { setModalHeaderDescription };
