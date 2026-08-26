/* SoAI - Shared UI loading buttons service [frontend/assets/ts/core/ui/loadingbuttons/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import { dom } from '@core/dom/dom.ts';
import { setAriaBusy } from '@core/ui/controls/ariaBusy.ts';
import { createBusyDisabledToken, getBusyDisabledToken, setBusyDisabledState, type BusyDisabledTarget, type BusyDisabledToken } from '@core/ui/controls/busyDisabledState.ts';

interface LoadingButtonDomApi {
    getData: (element: Element, key: string) => string | null;
    setText: (element: Element, value: string) => void;
}

interface LoadingButtonTextOptions {
    textTarget?: HTMLElement | null;
    loadingText?: string;
    idleText?: string;
}

interface SetLoadingButtonOptions extends LoadingButtonTextOptions {
    ariaLive?: string | null;
}

interface SetButtonLoadingOptions {
    textTarget?: HTMLElement | null;
    loadingText?: string;
    idleText?: string;
    disableTargets?: Element[];
    ariaLive?: string | null;
}

const BUTTON_TEXT_SELECTOR = '[data-button-text]';

const coerceBusyDisabledTarget = (element: HTMLElement): BusyDisabledTarget | null => {
    if (element instanceof HTMLButtonElement) {
        return element;
    }
    if (element instanceof HTMLInputElement) {
        return element;
    }
    if (element instanceof HTMLSelectElement) {
        return element;
    }
    if (element instanceof HTMLTextAreaElement) {
        return element;
    }
    if (element instanceof HTMLAnchorElement) {
        return element;
    }
    return null;
};

const resolveButtonTextTarget = (button: HTMLElement, explicitTarget: HTMLElement | null): HTMLElement => {
    if (explicitTarget !== null) {
        return explicitTarget;
    }
    const candidate = dom.resolve(BUTTON_TEXT_SELECTOR, button);
    if (candidate instanceof HTMLElement) {
        return candidate;
    }
    return button;
};

const applyButtonLoadingText = (dom: LoadingButtonDomApi, button: HTMLElement, isLoading: boolean, options: LoadingButtonTextOptions): void => {
    const textTarget = resolveButtonTextTarget(button, options.textTarget ?? null);
    const nextText = isLoading ? options.loadingText || dom.getData(button, 'loadingText') || dom.getData(textTarget, 'loadingText') : options.idleText || dom.getData(button, 'idleText') || dom.getData(textTarget, 'idleText');
    if (isString(nextText) && nextText.length > 0) {
        dom.setText(textTarget, nextText);
    }
};

const applyButtonAriaLive = (button: HTMLElement, ariaLive: string | null | undefined): void => {
    if (isString(ariaLive) && ariaLive.length > 0) {
        button.setAttribute('aria-live', ariaLive);
        return;
    }
    if (button.hasAttribute('aria-live')) {
        button.removeAttribute('aria-live');
    }
};

const beginLoadingButton = (button: BusyDisabledTarget): BusyDisabledToken => {
    return setBusyDisabledState(button, {
        isBusy: true,
        reuseExistingToken: true,
        createToken: createBusyDisabledToken,
        spinner: 'overlay'
    });
};

const endLoadingButton = (button: BusyDisabledTarget, token: BusyDisabledToken): void => {
    setBusyDisabledState(button, { isBusy: false, token });
};

const clearLoadingButtonIfNeeded = (button: BusyDisabledTarget): void => {
    const token = getBusyDisabledToken(button);
    if (token !== null) {
        endLoadingButton(button, token);
    }
};

const beginLoadingButtonWithClear = (button: BusyDisabledTarget): (() => void) => {
    const token = setBusyDisabledState(button, {
        isBusy: true,
        createToken: createBusyDisabledToken,
        spinner: 'overlay'
    });
    let isActive = true;
    return (): void => {
        if (!isActive) {
            return;
        }
        isActive = false;
        endLoadingButton(button, token);
    };
};

const setLoadingButtonState = (dom: LoadingButtonDomApi, button: HTMLElement, isLoading: boolean, options: SetLoadingButtonOptions = {}): void => {
    const busyTarget = coerceBusyDisabledTarget(button);
    if (busyTarget !== null) {
        if (isLoading) {
            beginLoadingButton(busyTarget);
        } else {
            clearLoadingButtonIfNeeded(busyTarget);
        }
    } else if (isLoading) {
        setAriaBusy(button, true);
    } else {
        setAriaBusy(button, false);
    }

    applyButtonAriaLive(button, options.ariaLive);
    applyButtonLoadingText(dom, button, isLoading, options);
};

export { BUTTON_TEXT_SELECTOR, beginLoadingButton, beginLoadingButtonWithClear, clearLoadingButtonIfNeeded, coerceBusyDisabledTarget, endLoadingButton, setLoadingButtonState };
export type { LoadingButtonDomApi, SetButtonLoadingOptions, SetLoadingButtonOptions };
