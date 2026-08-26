/* SoAI - Shared frontend navigation events [frontend/assets/ts/core/navigationEvents.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getEventBus } from '@core/EventBus.ts';
import type { NavigationDetail } from '@core/routing/router/types.ts';
import { isFunction, isObject, isString } from '@core/typeGuards.ts';

type NavigationEventDetail = NavigationDetail;

type NavigationEventHandler = (detail: NavigationEventDetail | null) => void;

type SubscribeOptions = AddEventListenerOptions;

const NAVIGATION_EVENTS = Object.freeze({
    START: 'router:navigation:start',
    COMPLETE: 'router:navigation:complete',
    ERROR: 'router:navigation:error'
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

const subscribe = (eventName: string, handler: NavigationEventHandler, options: SubscribeOptions = {}): (() => void) => {
    if (!isFunction(handler)) {
        throw new Error('Navigation event handler must be a function');
    }
    return getEventBus().on(
        eventName,
        (event: Event) => {
            if (event instanceof CustomEvent) {
                const detail = isObject(event.detail) ? event.detail : null;
                handler(isNavigationEventDetail(detail) ? detail : null);
                return;
            }
            handler(null);
        },
        options
    );
};

const onNavigationStart = (handler: NavigationEventHandler, options: SubscribeOptions = {}): (() => void) => {
    return subscribe(NAVIGATION_EVENTS.START, handler, options);
};

const onNavigationComplete = (handler: NavigationEventHandler, options: SubscribeOptions = {}): (() => void) => {
    return subscribe(NAVIGATION_EVENTS.COMPLETE, handler, options);
};

const onNavigationError = (handler: NavigationEventHandler, options: SubscribeOptions = {}): (() => void) => {
    return subscribe(NAVIGATION_EVENTS.ERROR, handler, options);
};

export { NAVIGATION_EVENTS, emitNavigationEvent, onNavigationStart, onNavigationComplete, onNavigationError };

export type { NavigationEventDetail, NavigationEventHandler, SubscribeOptions };
