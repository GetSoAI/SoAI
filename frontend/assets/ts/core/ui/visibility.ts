/* SoAI - Shared UI visibility [frontend/assets/ts/core/ui/visibility.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CSS_CLASSES } from '@core/cssConstants.ts';
import { dom } from '@core/dom/dom.ts';

type VisibilityMode = 'hiddenAttribute' | 'hiddenClass';

interface VisibilityOptions {
    ariaHidden?: boolean | undefined;
    hiddenClassName?: string | undefined;
    mode?: VisibilityMode | undefined;
}

export const setVisibilityState = (element: HTMLElement | null, visible: boolean, options: VisibilityOptions = {}): void => {
    if (!element) {
        return;
    }
    const mode = options.mode ?? 'hiddenClass';
    const hiddenClassName = options.hiddenClassName ?? CSS_CLASSES.HIDDEN;
    if (mode === 'hiddenAttribute') {
        element.hidden = !visible;
    } else {
        dom.toggleClass(element, hiddenClassName, !visible);
    }
    if (options.ariaHidden === true) {
        element.setAttribute('aria-hidden', visible ? 'false' : 'true');
    }
    dom.flush();
};

export const setElementVisibility = (element: HTMLElement | null, visible: boolean): void => {
    setVisibilityState(element, visible);
};

export const showElement = (element: HTMLElement | null): void => {
    setElementVisibility(element, true);
};

export const hideElement = (element: HTMLElement | null): void => {
    setElementVisibility(element, false);
};

export const toggleHidden = (element: HTMLElement | null, isHidden: boolean): void => {
    setVisibilityState(element, !isHidden);
};

export type { VisibilityMode, VisibilityOptions };
