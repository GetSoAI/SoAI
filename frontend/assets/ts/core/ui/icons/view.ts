/* SoAI - Shared UI icons rendering [frontend/assets/ts/core/ui/icons/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { replaceChildrenFromTrustedHtml } from '@core/dom/html.ts';
import { isTrustedHtml, toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { EMPTY_UI_HTML, uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import { isString } from '@core/typeGuards.ts';

interface IconSlotOptions {
    className?: string | undefined;
    hidden?: boolean | undefined;
}

const resolveIconMarkup = (icon: TrustedHtml | string): TrustedHtml => {
    if (isTrustedHtml(icon)) {
        return icon;
    }
    if (isString(icon)) {
        return toTrustedUiHtml(icon);
    }
    throw new Error('Icon slot requires HTML markup');
};

const renderIconSlot = (icon: TrustedHtml | string, options: IconSlotOptions = {}): TrustedHtml => {
    const iconMarkup = resolveIconMarkup(icon);
    if (!iconMarkup.html.trim()) {
        return EMPTY_UI_HTML;
    }
    const className = isString(options.className) && options.className.trim() ? options.className.trim() : 'ui-icon';
    const hiddenAttribute = options.hidden === false ? EMPTY_UI_HTML : uiHtml` aria-hidden="true"`;
    return uiHtml`<span class="${uiAttr(className)}"${hiddenAttribute}>${iconMarkup}</span>`;
};

const createIconSlot = (documentRef: Document, icon: TrustedHtml, options: IconSlotOptions = {}): HTMLSpanElement => {
    const slot = documentRef.createElement('span');
    const className = isString(options.className) && options.className.trim() ? options.className.trim() : 'ui-icon';
    slot.className = className;
    if (options.hidden !== false) {
        slot.setAttribute('aria-hidden', 'true');
    }
    const markup = resolveIconMarkup(icon).html;
    if (markup) {
        replaceChildrenFromTrustedHtml({ element: slot, html: icon });
    }
    return slot;
};

const setIconSlot = (slot: HTMLElement, icon: TrustedHtml, options: IconSlotOptions = {}): void => {
    const className = isString(options.className) && options.className.trim() ? options.className.trim() : 'ui-icon';
    slot.className = className;
    if (options.hidden === false) {
        slot.removeAttribute('aria-hidden');
    } else {
        slot.setAttribute('aria-hidden', 'true');
    }
    const markup = resolveIconMarkup(icon).html;
    if (markup) {
        replaceChildrenFromTrustedHtml({ element: slot, html: icon });
    } else {
        slot.replaceChildren();
    }
};

export { createIconSlot, renderIconSlot, setIconSlot };
export type { IconSlotOptions };
