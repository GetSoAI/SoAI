/* SoAI - Shared frontend navigation events [frontend/assets/ts/core/navigationEvents.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getEventBus } from '@core/EventBus.ts';
import type { NavigationDetail } from '@core/routing/router/types.ts';
import { isFunction, isObject, isString } from '@core/typeGuards.ts';

interface NavigationPresentation {
    readonly paneId: string | null;
    readonly mountGeneration: symbol | null;
    readonly focused: boolean;
}

type NavigationEventDetail = NavigationDetail & Partial<NavigationPresentation> & { readonly isCurrentPresentation?: () => boolean };

type NavigationEventHandler = (detail: NavigationEventDetail | null) => void;

type SubscribeOptions = AddEventListenerOptions;

const NAVIGATION_EVENTS = Object.freeze({
    START: 'router:navigation:start',
    COMPLETE: 'router:navigation:complete',
    ERROR: 'router:navigation:error',
    FOCUS: 'router:focus:change'
});

const emitNavigationEvent = (eventName: string, detail: NavigationEventDetail): void => {
    getEventBus().emit(eventName, detail);
};

const isNavigationEventDetail = <T>(value: T): value is T & NavigationEventDetail => {
    if (!isObject(value)) {
        return false;
    }
    return 'phase' in value && isString(value.phase) && 'component' in value && (isString(value.component) || value.component === null);
};

const subscribe = (eventNames: readonly string[], handler: NavigationEventHandler, options: SubscribeOptions = {}, focused = false): (() => void) => {
    if (!isFunction(handler)) {
        throw new Error('Navigation event handler must be a function');
    }
    const releases = eventNames.map((eventName) =>
        getEventBus().on(
            eventName,
            (event: Event) => {
                if (event instanceof CustomEvent) {
                    const detail = isObject(event.detail) ? event.detail : null;
                    if (isNavigationEventDetail(detail)) {
                        if (!focused || (detail.focused !== false && detail.isCurrentPresentation?.() !== false)) handler(detail);
                    } else handler(null);
                    return;
                }
                handler(null);
            },
            options
        )
    );
    return () => releases.forEach((release) => release());
};

const onNavigationStart = (handler: NavigationEventHandler, options: SubscribeOptions = {}): (() => void) => {
    return subscribe([NAVIGATION_EVENTS.START], handler, options);
};

const onNavigationComplete = (handler: NavigationEventHandler, options: SubscribeOptions = {}): (() => void) => {
    return subscribe([NAVIGATION_EVENTS.COMPLETE], handler, options);
};

const onNavigationError = (handler: NavigationEventHandler, options: SubscribeOptions = {}): (() => void) => {
    return subscribe([NAVIGATION_EVENTS.ERROR], handler, options);
};

const onFocusedNavigation = (handler: NavigationEventHandler, { phase = 'complete', ...options }: SubscribeOptions & { phase?: 'start' | 'complete' | 'error' } = {}): (() => void) => {
    const eventNames = phase === 'complete' ? [NAVIGATION_EVENTS.COMPLETE, NAVIGATION_EVENTS.FOCUS] : [phase === 'start' ? NAVIGATION_EVENTS.START : NAVIGATION_EVENTS.ERROR];
    return subscribe(eventNames, handler, options, true);
};

export { NAVIGATION_EVENTS, emitNavigationEvent, onNavigationStart, onNavigationComplete, onNavigationError, onFocusedNavigation };

export type { NavigationEventDetail, NavigationEventHandler, NavigationPresentation, SubscribeOptions };
