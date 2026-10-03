/* SoAI - Shared UI ARIA busy-state control [frontend/assets/ts/core/ui/controls/ariaBusy.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CSS_CLASSES } from '@core/cssConstants.ts';

const setAriaBusy = (element: Element, busy: boolean): void => {
    if (element.matches('button')) {
        element.classList.toggle(CSS_CLASSES.BUSY_CONTROL, busy);
    }
    if (busy) {
        element.setAttribute('aria-busy', 'true');
        return;
    }
    element.removeAttribute('aria-busy');
};

const setAriaBusyForElements = (elements: readonly Element[], busy: boolean): void => {
    for (const element of elements) {
        setAriaBusy(element, busy);
    }
};

export { setAriaBusy, setAriaBusyForElements };
