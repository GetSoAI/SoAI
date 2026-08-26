/* SoAI - Shared UI busy disabled state [frontend/assets/ts/core/ui/controls/busyDisabledState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { isString } from '@core/typeGuards.ts';
import { setAriaBusy } from '@core/ui/controls/ariaBusy.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';

type BusyDisabledTarget = HTMLButtonElement | HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement | HTMLAnchorElement;

type BusyDisabledToken = string;

type BusyDisabledStartArguments = {
    isBusy: true;
    createToken: () => BusyDisabledToken;
    reuseExistingToken?: boolean;
    tooltip?: string | null;
    spinner?: 'overlay' | 'none' | undefined;
};

type BusyDisabledStopArguments = {
    isBusy: false;
    token: BusyDisabledToken;
};

const DATASET_KEY_PATTERN = /^[a-z][a-zA-Z0-9]*$/;

const toDataAttributeName = (key: string): string => {
    if (!DATASET_KEY_PATTERN.test(key)) {
        throw new Error(`Busy state dataset key must be lowerCamelCase: ${key}`);
    }
    return `data-${key.replace(/[A-Z]/g, (match) => `-${match.toLowerCase()}`)}`;
};

const readDataAttribute = (element: BusyDisabledTarget, key: string): string | null => element.getAttribute(toDataAttributeName(key));

const writeDataAttribute = (element: BusyDisabledTarget, key: string, value: string): void => {
    element.setAttribute(toDataAttributeName(key), value);
};

const clearDataAttribute = (element: BusyDisabledTarget, key: string): void => {
    element.removeAttribute(toDataAttributeName(key));
};

const BUSY_TOKEN_KEY = 'soaiBusyToken';
const BUSY_PREV_DISABLED_KEY = 'soaiBusyPrevDisabled';
const BUSY_PREV_ARIA_DISABLED_KEY = 'soaiBusyPrevAriaDisabled';
const BUSY_PREV_TABINDEX_KEY = 'soaiBusyPrevTabindex';
const BUSY_PREV_TOOLTIP_KEY = 'soaiBusyPrevTooltip';
const BUSY_PREV_SPINNER_KEY = 'soaiBusyPrevSpinner';

const SPINNER_ATTRIBUTE = 'data-busy-spinner';

const storePrevSpinner = (element: BusyDisabledTarget): void => {
    const existing = readDataAttribute(element, BUSY_PREV_SPINNER_KEY);
    if (existing !== null) {
        return;
    }
    const prev = element.getAttribute(SPINNER_ATTRIBUTE);
    writeDataAttribute(element, BUSY_PREV_SPINNER_KEY, prev === null ? '' : prev);
};

const restorePrevSpinner = (element: BusyDisabledTarget): void => {
    const prev = readDataAttribute(element, BUSY_PREV_SPINNER_KEY);
    if (prev === null) {
        return;
    }
    if (prev === '') {
        element.removeAttribute(SPINNER_ATTRIBUTE);
    } else {
        element.setAttribute(SPINNER_ATTRIBUTE, prev);
    }
    clearDataAttribute(element, BUSY_PREV_SPINNER_KEY);
};

const readTooltip = (element: Element): string => element.getAttribute('data-tooltip') ?? '';

const defaultBusyTooltip = (): string => i18n.t('common.loading');

const storePrevTooltip = (element: BusyDisabledTarget): void => {
    const existing = readDataAttribute(element, BUSY_PREV_TOOLTIP_KEY);
    if (existing !== null) {
        return;
    }
    writeDataAttribute(element, BUSY_PREV_TOOLTIP_KEY, readTooltip(element));
};

const restorePrevTooltip = (element: BusyDisabledTarget): void => {
    const prev = readDataAttribute(element, BUSY_PREV_TOOLTIP_KEY);
    if (prev === null) {
        return;
    }
    setTooltipText(element, prev);
    clearDataAttribute(element, BUSY_PREV_TOOLTIP_KEY);
};

const storePrevAriaDisabled = (element: BusyDisabledTarget): void => {
    const existing = readDataAttribute(element, BUSY_PREV_ARIA_DISABLED_KEY);
    if (existing !== null) {
        return;
    }
    const prev = element.getAttribute('aria-disabled');
    writeDataAttribute(element, BUSY_PREV_ARIA_DISABLED_KEY, prev === null ? '' : prev);
};

const restorePrevAriaDisabled = (element: BusyDisabledTarget): void => {
    const prev = readDataAttribute(element, BUSY_PREV_ARIA_DISABLED_KEY);
    if (prev === null) {
        return;
    }
    if (prev === '') {
        element.removeAttribute('aria-disabled');
    } else {
        element.setAttribute('aria-disabled', prev);
    }
    clearDataAttribute(element, BUSY_PREV_ARIA_DISABLED_KEY);
};

const storePrevTabindex = (element: BusyDisabledTarget): void => {
    const existing = readDataAttribute(element, BUSY_PREV_TABINDEX_KEY);
    if (existing !== null) {
        return;
    }
    const prev = element.getAttribute('tabindex');
    writeDataAttribute(element, BUSY_PREV_TABINDEX_KEY, prev === null ? '' : prev);
};

const restorePrevTabindex = (element: BusyDisabledTarget): void => {
    const prev = readDataAttribute(element, BUSY_PREV_TABINDEX_KEY);
    if (prev === null) {
        return;
    }
    if (prev === '') {
        element.removeAttribute('tabindex');
    } else {
        element.setAttribute('tabindex', prev);
    }
    clearDataAttribute(element, BUSY_PREV_TABINDEX_KEY);
};

const storePrevDisabled = (element: BusyDisabledTarget): void => {
    const existing = readDataAttribute(element, BUSY_PREV_DISABLED_KEY);
    if (existing !== null) {
        return;
    }
    if ('disabled' in element) {
        writeDataAttribute(element, BUSY_PREV_DISABLED_KEY, element.disabled ? 'true' : 'false');
        return;
    }
    writeDataAttribute(element, BUSY_PREV_DISABLED_KEY, '');
};

const restorePrevDisabled = (element: BusyDisabledTarget): void => {
    const prev = readDataAttribute(element, BUSY_PREV_DISABLED_KEY);
    if (prev === null) {
        return;
    }
    if ('disabled' in element) {
        if (prev === 'true') {
            element.disabled = true;
        } else if (prev === 'false') {
            element.disabled = false;
        }
    }
    clearDataAttribute(element, BUSY_PREV_DISABLED_KEY);
};

function setBusyDisabledState(target: BusyDisabledTarget, inputArguments: BusyDisabledStartArguments): BusyDisabledToken;
function setBusyDisabledState(target: BusyDisabledTarget, inputArguments: BusyDisabledStopArguments): void;
function setBusyDisabledState(target: BusyDisabledTarget, inputArguments: BusyDisabledStartArguments | BusyDisabledStopArguments): BusyDisabledToken | void {
    if (inputArguments.isBusy) {
        if (inputArguments.reuseExistingToken === true) {
            const existingToken = readDataAttribute(target, BUSY_TOKEN_KEY);
            if (isString(existingToken) && existingToken.length > 0) {
                return existingToken;
            }
        }
        const nextToken = inputArguments.createToken();
        if (!isString(nextToken) || nextToken.length === 0) {
            throw new Error('Busy state createToken() must return a non-empty token');
        }

        writeDataAttribute(target, BUSY_TOKEN_KEY, nextToken);
        storePrevDisabled(target);
        storePrevAriaDisabled(target);
        storePrevTabindex(target);
        storePrevTooltip(target);
        storePrevSpinner(target);

        setAriaBusy(target, true);
        target.setAttribute('aria-disabled', 'true');

        if ('disabled' in target) {
            target.disabled = true;
        } else {
            target.setAttribute('tabindex', '-1');
        }

        const tooltipText = isString(inputArguments.tooltip) ? inputArguments.tooltip : inputArguments.tooltip === null ? '' : defaultBusyTooltip();
        setTooltipText(target, tooltipText);

        const spinnerMode = inputArguments.spinner === 'none' ? 'none' : 'overlay';
        target.setAttribute(SPINNER_ATTRIBUTE, spinnerMode);

        return nextToken;
    }

    if (!isString(inputArguments.token) || inputArguments.token.length === 0) {
        throw new Error('Busy state requires a token to clear busy state');
    }
    if (readDataAttribute(target, BUSY_TOKEN_KEY) !== inputArguments.token) {
        return;
    }

    setAriaBusy(target, false);
    target.removeAttribute('aria-disabled');

    restorePrevDisabled(target);
    restorePrevAriaDisabled(target);
    restorePrevTabindex(target);
    restorePrevTooltip(target);
    restorePrevSpinner(target);
    clearDataAttribute(target, BUSY_TOKEN_KEY);
}

let busyTokenSequence = 0;

const createBusyDisabledToken = (): BusyDisabledToken => {
    busyTokenSequence += 1;
    return String(busyTokenSequence);
};

const getBusyDisabledToken = (target: BusyDisabledTarget): BusyDisabledToken | null => {
    const token = readDataAttribute(target, BUSY_TOKEN_KEY);
    return isString(token) && token.length > 0 ? token : null;
};

export { createBusyDisabledToken, getBusyDisabledToken, setBusyDisabledState };
export type { BusyDisabledTarget, BusyDisabledToken };
