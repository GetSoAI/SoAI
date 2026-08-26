/* SoAI - Shared UI ARIA busy-state control [frontend/assets/ts/core/ui/controls/ariaBusy.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const setAriaBusy = (element: Element, busy: boolean): void => {
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
