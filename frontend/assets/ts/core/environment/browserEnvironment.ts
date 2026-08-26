/* SoAI - Frontend browser environment access [frontend/assets/ts/core/environment/browserEnvironment.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dispatchCustomEvent, getBody, getDocument, getDocumentElement, getElementByIdStrict, getEventHub, getGlobalScope, getWindow, requireDocument } from '@core/environment/globalScope.ts';
import { isFunction, isString } from '@core/typeGuards.ts';

const getLocation = (): Location => {
    const location = getWindow().location;
    if (!location || (!isString(location.href) && !isString(location.toString?.()))) {
        throw new Error('Location is required for environment operations');
    }
    return location;
};

const getHistory = (): History => {
    const history = getWindow().history;
    if (!history || !isFunction(history.pushState) || !isFunction(history.replaceState)) {
        throw new Error('History API is required for environment operations');
    }
    return history;
};

const getPerformance = (): Performance => {
    const perf = getGlobalScope().performance;
    if (!perf || !isFunction(perf.getEntriesByType)) {
        throw new Error('Performance API is required for environment operations');
    }
    return perf;
};

const requirePerformanceNow = (): (() => number) => {
    const perf = getPerformance();
    if (!isFunction(perf.now)) {
        throw new Error('Performance.now is required for timing operations');
    }
    return (): number => perf.now();
};

const getRequestAnimationFrame = (): typeof requestAnimationFrame => {
    const win = getWindow();
    if (!isFunction(win.requestAnimationFrame)) {
        throw new Error('Window.requestAnimationFrame must be available for environment operations');
    }
    return (callback: FrameRequestCallback): number => {
        return win.requestAnimationFrame(callback);
    };
};

const getCancelAnimationFrame = (): typeof cancelAnimationFrame => {
    const win = getWindow();
    if (!isFunction(win.cancelAnimationFrame)) {
        throw new Error('Window.cancelAnimationFrame must be available for environment operations');
    }
    return (handle: number): void => {
        win.cancelAnimationFrame(handle);
    };
};

const getPrompt = (): ((message?: string, _default?: string) => string | null) => {
    const win = getWindow();
    if (!isFunction(win.prompt)) {
        throw new Error('Window.prompt must be available for environment operations');
    }
    return (message?: string, defaultValue?: string): string | null => {
        return win.prompt(message, defaultValue);
    };
};

const getWindowOpen = (): ((url?: string | URL, target?: string, features?: string) => Window | null) => {
    const win = getWindow();
    if (!isFunction(win.open)) {
        throw new Error('Window.open must be available for environment operations');
    }
    return (url?: string | URL, target?: string, features?: string): Window | null => {
        return win.open(url, target, features);
    };
};

const getComputedStyleStrict = (element: Element): CSSStyleDeclaration => {
    const win = getWindow();
    if (!isFunction(win.getComputedStyle)) {
        throw new Error('Window.getComputedStyle must be available for environment operations');
    }
    return win.getComputedStyle(element);
};

const getMatchMedia = (): ((query: string) => MediaQueryList) => {
    const win = getWindow();
    if (!isFunction(win.matchMedia)) {
        throw new Error('Window.matchMedia must be available for environment operations');
    }
    return (query: string): MediaQueryList => {
        return win.matchMedia(query);
    };
};

const getScrollTo = (): ((options?: ScrollToOptions) => void) => {
    const win = getWindow();
    if (!isFunction(win.scrollTo)) {
        throw new Error('Window.scrollTo must be available for environment operations');
    }
    return (options?: ScrollToOptions): void => {
        win.scrollTo(options);
    };
};

const getMutationObserverCtor = (): typeof MutationObserver => {
    const scope = getGlobalScope();
    const MutationObserverCtor = scope.MutationObserver;
    if (!isFunction(MutationObserverCtor)) {
        throw new Error('MutationObserver constructor is required for environment operations');
    }
    return MutationObserverCtor;
};

const getStructuredClone = (): typeof structuredClone => {
    const scope = getGlobalScope();
    const structuredCloneFunctionValue = scope.structuredClone;
    if (!isFunction(structuredCloneFunctionValue)) {
        throw new Error('structuredClone is required for environment operations');
    }
    return structuredCloneFunctionValue;
};

const getEventConstructor = (): typeof Event => {
    const scope = getGlobalScope();
    const eventCtor = scope.Event;
    if (!isFunction(eventCtor)) {
        throw new Error('Event constructor is required for environment operations');
    }
    return eventCtor;
};

const getBroadcastChannelCtor = (): typeof BroadcastChannel => {
    const scope = getGlobalScope();
    const ctor = scope.BroadcastChannel;
    if (!isFunction(ctor)) {
        throw new Error('BroadcastChannel constructor is required for environment operations');
    }
    return ctor;
};

const getAbortControllerCtor = (): typeof AbortController => {
    const scope = getGlobalScope();
    const ctor = scope.AbortController;
    if (!isFunction(ctor)) {
        throw new Error('AbortController constructor is required for environment operations');
    }
    return ctor;
};

const getSharedWorkerCtor = (): typeof SharedWorker | null => {
    const scope = getGlobalScope();
    return isFunction(scope.SharedWorker) ? scope.SharedWorker : null;
};

const getDevicePixelRatio = (): number => {
    const dpr = getWindow().devicePixelRatio;
    if (!Number.isFinite(dpr)) {
        throw new Error('devicePixelRatio must be finite for environment operations');
    }
    return dpr;
};

export { dispatchCustomEvent, getAbortControllerCtor, getBody, getBroadcastChannelCtor, getCancelAnimationFrame, getComputedStyleStrict, getDevicePixelRatio, getDocument, getDocumentElement, getElementByIdStrict, getEventConstructor, getEventHub, getGlobalScope, getHistory, getLocation, getMatchMedia, getMutationObserverCtor, getPerformance, getPrompt, getRequestAnimationFrame, getScrollTo, getSharedWorkerCtor, getStructuredClone, getWindow, getWindowOpen, requireDocument, requirePerformanceNow };
