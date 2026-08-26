/* SoAI - UI state persistence and synchronization [frontend/assets/ts/core/state/UIStateManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureArray } from '@core/normalize.ts';
import { isFunction, isNullOrUndefined, isObject } from '@core/typeGuards.ts';
import { setAriaBusy } from '@core/ui/controls/ariaBusy.ts';
import { createBusyDisabledToken, getBusyDisabledToken, setBusyDisabledState } from '@core/ui/controls/busyDisabledState.ts';
import { coerceBusyDisabledTarget, setLoadingButtonState, type SetButtonLoadingOptions } from '@core/ui/loadingbuttons/service.ts';

const DATASET_KEY_PATTERN = /^[a-z][a-zA-Z0-9]*$/;

const toDataAttributeName = (key: string): string => {
    if (!DATASET_KEY_PATTERN.test(key)) {
        throw new Error(`UIStateManager dataset keys must be lowerCamelCase: ${key}`);
    }
    return `data-${key.replace(/[A-Z]/g, (match) => `-${match.toLowerCase()}`)}`;
};

interface DomStateApi {
    resolve: (selector: string, context?: Element | null) => Element | null;
    resolveAll: (selector: string, context?: Element | null) => Element[];
    toggleClass: (element: Element, className: string, force?: boolean) => void;
    setText: (element: Element, value: string) => void;
    setHTML: (element: Element, value: string, options?: { escape?: boolean }) => void;
    getData: (element: Element, key: string) => string | null;
}

type ElementResolver = (target: string | Element | null | undefined) => HTMLElement | null;

interface UIStateManagerOptions {
    dom: DomStateApi;
    resolveElement: ElementResolver;
    defaultHiddenClass: string;
}

interface ToggleHiddenOptions {
    className?: string;
    focusOnShow?: boolean;
}

interface SetBusyOptions {
    disable?: boolean;
    inert?: boolean;
    ariaLive?: string | null;
}

class UIStateManager {
    dom: DomStateApi;
    resolveElement: ElementResolver;
    defaultHiddenClass: string;

    constructor({ dom, resolveElement, defaultHiddenClass }: UIStateManagerOptions) {
        this.dom = dom;
        this.resolveElement = resolveElement;
        this.defaultHiddenClass = defaultHiddenClass;
    }

    resolve(target: string | Element | null | undefined): HTMLElement | null {
        return this.resolveElement(target);
    }

    getUI(selector: string, context: Element | null = null): Element | null {
        return this.dom.resolve(selector, context);
    }

    queryUI(selector: string, context: Element | null = null): Element[] {
        return this.dom.resolveAll(selector, context);
    }

    toggleHidden(targets: string | string[] | Element | Element[] | null | undefined, shouldHide: boolean, options: ToggleHiddenOptions = {}): void {
        const { className = this.defaultHiddenClass, focusOnShow = false } = options;
        const hide = !!shouldHide;
        ensureArray(targets).forEach((target) => {
            const element = this.resolveElement(target);
            if (!element) {
                return;
            }
            this.dom.toggleClass(element, className, hide);
            element.toggleAttribute('aria-hidden', hide);
            if (!hide && focusOnShow && isFunction(element.focus)) {
                element.focus({ preventScroll: true });
            }
        });
    }

    setBusy(target: string | Element | null | undefined, isBusy: boolean, options: SetBusyOptions = {}): HTMLElement | null {
        const { disable = true, inert = false, ariaLive = null } = options;
        const element = this.resolveElement(target);
        if (!element) {
            return null;
        }
        const busy = !!isBusy;
        if (disable) {
            const busyTarget = coerceBusyDisabledTarget(element);
            if (busyTarget) {
                if (busy) {
                    setBusyDisabledState(busyTarget, { isBusy: true, reuseExistingToken: true, createToken: createBusyDisabledToken, spinner: 'none' });
                } else {
                    const token = getBusyDisabledToken(busyTarget);
                    if (token) {
                        setBusyDisabledState(busyTarget, { isBusy: false, token });
                    }
                }
            } else {
                setAriaBusy(element, busy);
            }
        } else {
            setAriaBusy(element, busy);
        }
        if (inert) {
            element.toggleAttribute('inert', busy);
        }
        if (ariaLive) {
            element.setAttribute('aria-live', ariaLive);
        } else if (element.hasAttribute('aria-live')) {
            element.removeAttribute('aria-live');
        }
        return element;
    }

    setText(target: string | Element | null | undefined, value: string | null | undefined): HTMLElement | null {
        const element = this.resolveElement(target);
        if (element) {
            this.dom.setText(element, String(value ?? ''));
        }
        return element;
    }

    setHTML(target: string | Element | null | undefined, value: string | null | undefined, options: { escape?: boolean } = {}): HTMLElement | null {
        const element = this.resolveElement(target);
        if (element) {
            const { escape = false } = options;
            this.dom.setHTML(element, String(value ?? ''), { escape });
        }
        return element;
    }

    updateDataset(target: string | Element | null | undefined, dataset: Record<string, string | null | undefined> = {}): HTMLElement | null {
        const element = this.resolveElement(target);
        if (!element || !isObject(dataset)) {
            return null;
        }
        Object.entries(dataset).forEach(([key, value]) => {
            const attributeName = toDataAttributeName(key);
            if (isNullOrUndefined(value)) {
                element.removeAttribute(attributeName);
            } else {
                element.setAttribute(attributeName, String(value));
            }
        });
        return element;
    }

    toggleClass(targets: string | string[] | Element | Element[] | null | undefined, className: string, force?: boolean): void {
        ensureArray(targets).forEach((target) => {
            const element = this.resolveElement(target);
            if (element) {
                this.dom.toggleClass(element, className, force);
            }
        });
    }

    setButtonLoading(target: string | Element | null | undefined, loading: boolean, options: SetButtonLoadingOptions = {}): HTMLElement | null {
        const button = this.resolveElement(target);
        if (!button) {
            return null;
        }

        const isLoading = !!loading;
        const { textTarget, disableTargets = [], ...loadingOptions } = options;
        setLoadingButtonState(this.dom, button, isLoading, {
            ...loadingOptions,
            textTarget: this.resolveElement(textTarget)
        });

        if (disableTargets.length) {
            disableTargets.forEach((entry) => {
                const element = this.resolveElement(entry);
                if (element) {
                    this.setBusy(element, isLoading, { disable: true });
                }
            });
        }

        return button;
    }
}

export { UIStateManager };
export type { UIStateManagerOptions, DomStateApi, ElementResolver, ToggleHiddenOptions, SetBusyOptions, SetButtonLoadingOptions };
