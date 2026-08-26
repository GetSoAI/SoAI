/* SoAI - Shared frontend loading state [frontend/assets/ts/core/loadingState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CSS_CLASSES } from '@core/cssConstants.ts';
import { dom } from '@core/dom/dom.ts';
import { isBoolean, isElementNode, isString } from '@core/typeGuards.ts';
import { setAriaBusy } from '@core/ui/controls/ariaBusy.ts';

const DEFAULT_ELEMENT_ID = 'main-content';
const DEFAULT_HANDLE = 'page';
const LOADING_CONTAINER_CLASS = 'loading-container';
const SPINNER_CLASS = 'loading-spinner';
const DEFAULT_LOADING_TEXT = 'Loading...';

interface ResolveOptions {
    strict?: boolean;
}

interface ApplyOptions {
    withSpinner?: boolean;
    strict?: boolean;
}

interface LoadingStateEntry {
    element: Element;
    text: string;
}

const resolveElement = (target: Element | string, { strict = false }: ResolveOptions = {}): Element | null => {
    if (isElementNode(target)) return target;
    if (isString(target) && target.trim()) {
        const selector = target.trim();
        const resolved = dom.resolve(selector.startsWith('#') ? selector : `#${selector}`) || dom.resolve(selector);
        if (resolved) return resolved;
    }
    if (strict) {
        throw new Error('Loading state target element must exist');
    }
    return null;
};

const normalizeLoadingFlag = (value: boolean): boolean => {
    if (!isBoolean(value)) {
        throw new TypeError('Loading state must be a boolean');
    }
    return value;
};

const normalizeLoadingText = (text: string): string => {
    if (!isString(text) || !text.trim()) {
        throw new TypeError('Loading text must be a non-empty string');
    }
    return text.trim();
};

const ensureSpinner = (element: Element): Element => {
    const existing = dom.resolve(`.${LOADING_CONTAINER_CLASS}`, element);
    if (existing) {
        if (!dom.resolve(`.${SPINNER_CLASS}`, existing)) {
            const spinnerIcon = dom.getDocument().createElement('span');
            dom.addClass(spinnerIcon, SPINNER_CLASS);
            dom.setAttribute(spinnerIcon, 'aria-hidden', 'true');
            existing.insertBefore(spinnerIcon, existing.firstChild);
        }
        if (!dom.resolve('.loading-text', existing)) {
            const spinnerText = dom.getDocument().createElement('span');
            dom.addClass(spinnerText, 'loading-text');
            dom.appendChild(existing, spinnerText);
        }
        return existing;
    }

    const spinnerContainer = dom.getDocument().createElement('div');
    dom.setProperty(spinnerContainer, 'className', LOADING_CONTAINER_CLASS);

    const spinnerIcon = dom.getDocument().createElement('span');
    dom.addClass(spinnerIcon, SPINNER_CLASS);
    dom.setAttribute(spinnerIcon, 'aria-hidden', 'true');

    const spinnerText = dom.getDocument().createElement('span');
    dom.addClass(spinnerText, 'loading-text');

    dom.appendChild(spinnerContainer, spinnerIcon);
    dom.appendChild(spinnerContainer, spinnerText);
    dom.appendChild(element, spinnerContainer);

    return spinnerContainer;
};

const ensureSpinnerText = (spinner: Element, text: string): void => {
    let textElement = dom.resolve('.loading-text', spinner);
    if (!textElement) {
        textElement = dom.getDocument().createElement('span');
        dom.addClass(textElement, 'loading-text');
        dom.appendChild(spinner, textElement);
    }
    dom.setText(textElement, text);
};

const removeSpinner = (element: Element): void => {
    const spinner = dom.resolve(`.${LOADING_CONTAINER_CLASS}`, element);
    if (spinner) {
        dom.remove(spinner);
    }
};

const applyLoadingState = (target: Element | string, isLoading: boolean, loadingText: string = DEFAULT_LOADING_TEXT, options: ApplyOptions = {}): Element | null => {
    const { withSpinner = true, strict = false } = options;
    const loading = normalizeLoadingFlag(isLoading);
    const text = normalizeLoadingText(loadingText ?? DEFAULT_LOADING_TEXT);
    const element = resolveElement(target, { strict });
    if (!element) {
        return null;
    }
    setAriaBusy(element, loading);
    dom.setData(element, 'loadingText', loading ? text : null);
    dom.toggleClass(element, CSS_CLASSES.LOADING, loading);
    if (withSpinner) {
        if (loading) {
            const spinner = ensureSpinner(element);
            ensureSpinnerText(spinner, text);
        } else {
            removeSpinner(element);
        }
    } else if (!loading) {
        removeSpinner(element);
    }
    return element;
};

class LoadingStateManager {
    element: Element;

    constructor(element: Element) {
        this.element = element;
    }

    show(): void {
        applyLoadingState(this.element, true, DEFAULT_LOADING_TEXT, { strict: true });
    }

    hide(): void {
        applyLoadingState(this.element, false, DEFAULT_LOADING_TEXT, { strict: true });
    }

    updateText(text: string): void {
        applyLoadingState(this.element, true, text, { strict: true });
    }
}

class LoadingState {
    loadingStates: Map<string, LoadingStateEntry>;

    constructor() {
        this.loadingStates = new Map();
    }

    setState(elementId: string | null, isLoading: boolean, loadingText: string = DEFAULT_LOADING_TEXT): void {
        const loadingKey = elementId || DEFAULT_HANDLE;
        const target = elementId || DEFAULT_ELEMENT_ID;
        const element = applyLoadingState(target, isLoading, loadingText, { withSpinner: true }) || this.loadingStates.get(loadingKey)?.element;
        if (!element) {
            return;
        }

        if (normalizeLoadingFlag(isLoading)) {
            this.loadingStates.set(loadingKey, { element, text: loadingText });
            return;
        } else {
            this.loadingStates.delete(loadingKey);
            applyLoadingState(element, false, loadingText, { withSpinner: true });
        }
    }

    clearAll(): void {
        this.loadingStates.forEach(({ element }) => {
            applyLoadingState(element, false, DEFAULT_LOADING_TEXT, { withSpinner: true });
        });
        this.loadingStates.clear();
    }

    createManager(elementOrSelector: Element | string): LoadingStateManager {
        const element = resolveElement(elementOrSelector, { strict: true });
        if (!element) {
            throw new Error('Loading state target element must exist');
        }
        return new LoadingStateManager(element);
    }

    getActiveStates(): string[] {
        return Array.from(this.loadingStates.keys());
    }

    hasActiveStates(): boolean {
        return this.loadingStates.size > 0;
    }

    clearState(elementId: string | null): void {
        const loadingKey = elementId || DEFAULT_HANDLE;
        const state = this.loadingStates.get(loadingKey);
        if (state) {
            applyLoadingState(state.element, false, state.text || DEFAULT_LOADING_TEXT, { withSpinner: true });
            this.loadingStates.delete(loadingKey);
        }
    }

    show(loadingText: string = DEFAULT_LOADING_TEXT, elementId: string | null = null): string {
        this.setState(elementId, true, loadingText);
        return elementId || DEFAULT_HANDLE;
    }

    hide(handle: string | null = null): void {
        const key = isString(handle) && handle ? handle : DEFAULT_HANDLE;
        this.setState(key === DEFAULT_HANDLE ? null : key, false);
    }

    destroy(): void {
        this.clearAll();
    }
}

let sharedLoadingStateInstance: LoadingState | null = null;

const getSharedLoadingState = (): LoadingState => {
    if (!sharedLoadingStateInstance) {
        sharedLoadingStateInstance = new LoadingState();
    }
    return sharedLoadingStateInstance;
};

interface LoadingStateApi {
    create: () => LoadingState;
    createManager: (elementOrSelector: Element | string) => LoadingStateManager;
    setElementState: (target: Element | string, isLoading: boolean, loadingText?: string, options?: ApplyOptions) => Element | null;
    setState: (elementId: string | null, isLoading: boolean, loadingText?: string) => void;
    show: (message?: string, elementId?: string | null) => string;
    hide: (handle?: string | null) => void;
    clearAll: () => void;
    clearState: (elementId: string | null) => void;
    getActiveStates: () => string[];
    hasActiveStates: () => boolean;
}

const loadingState: LoadingStateApi = Object.freeze({
    create(): LoadingState {
        return new LoadingState();
    },
    createManager(elementOrSelector: Element | string): LoadingStateManager {
        return getSharedLoadingState().createManager(elementOrSelector);
    },
    setElementState(target: Element | string, isLoading: boolean, loadingText: string = DEFAULT_LOADING_TEXT, options: ApplyOptions = {}): Element | null {
        return applyLoadingState(target, isLoading, loadingText, options);
    },
    setState(elementId: string | null, isLoading: boolean, loadingText?: string): void {
        getSharedLoadingState().setState(elementId, isLoading, loadingText);
    },
    show(message: string = DEFAULT_LOADING_TEXT, elementId: string | null = null): string {
        return getSharedLoadingState().show(message, elementId);
    },
    hide(handle: string | null = null): void {
        getSharedLoadingState().hide(handle);
    },
    clearAll(): void {
        getSharedLoadingState().clearAll();
    },
    clearState(elementId: string | null): void {
        getSharedLoadingState().clearState(elementId);
    },
    getActiveStates(): string[] {
        return getSharedLoadingState().getActiveStates();
    },
    hasActiveStates(): boolean {
        return getSharedLoadingState().hasActiveStates();
    }
});

export { LoadingState, LoadingStateManager, loadingState };
