/* SoAI - Shared layout dropdown elements [frontend/assets/ts/core/layout/header/dropdownElements.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { isHTMLElement } from '@core/typeGuards.ts';

const requireHeaderDropdownElement = (selector: string, description: string, context: HTMLElement | null = null): HTMLElement => {
    const element = context ? dom.resolve(selector, context) : dom.resolve(selector);
    if (!isHTMLElement(element)) {
        throw new Error(`Header dropdown requires ${description} element (${selector})`);
    }
    return element;
};

const requireHeaderDropdownButton = (selector: string, description: string, context: HTMLElement | null = null): HTMLButtonElement => {
    const element = requireHeaderDropdownElement(selector, description, context);
    if (!(element instanceof HTMLButtonElement)) {
        throw new Error(`Header dropdown requires ${description} button (${selector})`);
    }
    return element;
};

export { requireHeaderDropdownButton, requireHeaderDropdownElement };
