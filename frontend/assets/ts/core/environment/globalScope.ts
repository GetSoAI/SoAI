/* SoAI - Shared environment global scope [frontend/assets/ts/core/environment/globalScope.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { assertNonEmptyString } from '@core/assertions.ts';
import { isFunction, isInstanceOf, isObject } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

type GlobalScopeType = typeof globalThis & {
    window?: Window;
    document?: Document;
    CustomEvent?: typeof CustomEvent;
    HTMLElement?: typeof HTMLElement;
    MutationObserver?: typeof MutationObserver;
    structuredClone?: typeof structuredClone;
    Event?: typeof Event;
    BroadcastChannel?: typeof BroadcastChannel;
    AbortController?: typeof AbortController;
    SharedWorker?: typeof SharedWorker;
    __SOAI_RUNTIME_CONFIG__?: JsonValue;
};

type EventHubType = Window | typeof globalThis | Document;

const globalScope: GlobalScopeType = globalThis;

let customEventCtorRef: typeof CustomEvent | null = null;
let eventHubRef: EventHubType | null = null;

const getGlobalScope = (): GlobalScopeType => globalScope;

const getDocument = (): Document => {
    const scopeDocument = globalScope.document;
    if (!scopeDocument) {
        throw new Error('Document is required for environment operations');
    }
    return scopeDocument;
};

const getWindow = (): Window => {
    const candidate = getGlobalScope().window;
    if (!candidate || !isFunction(candidate.addEventListener) || !isFunction(candidate.removeEventListener)) {
        throw new Error('Window is required for environment operations');
    }
    return candidate;
};

const getHTMLElementCtor = (): typeof HTMLElement => {
    const ctor = getGlobalScope().HTMLElement;
    if (!isFunction(ctor)) {
        throw new Error('HTMLElement constructor is required for environment operations');
    }
    return ctor;
};

const requireDocument = (): Document => {
    const doc = getDocument();
    if (!isFunction(doc.addEventListener) || !isFunction(doc.getElementById)) {
        throw new Error('Document API is required for environment operations');
    }
    return doc;
};

const getDocumentElement = (): HTMLElement => {
    const element = getDocument().documentElement;
    if (!element) {
        throw new Error('Document element is required for environment operations');
    }
    return element;
};

const getBody = (): HTMLBodyElement => {
    const body = getDocument().body;
    if (!body) {
        throw new Error('Document body is required for environment operations');
    }
    if (!(body instanceof HTMLBodyElement)) {
        throw new Error('Document body must be an HTMLBodyElement');
    }
    return body;
};

const getElementByIdStrict = (id: string): HTMLElement => {
    const normalizedId = assertNonEmptyString(id, 'Element id');
    const element = requireDocument().getElementById(normalizedId);
    if (!isInstanceOf(element, getHTMLElementCtor())) {
        throw new Error(`Element with id ${normalizedId} must exist`);
    }
    return element;
};

const getCustomEventCtor = (): typeof CustomEvent => {
    if (customEventCtorRef) {
        return customEventCtorRef;
    }
    if (isFunction(globalScope.CustomEvent)) {
        customEventCtorRef = globalScope.CustomEvent;
        return customEventCtorRef;
    }
    throw new Error('CustomEvent support is required');
};

const getEventHub = (): EventHubType => {
    if (eventHubRef) {
        return eventHubRef;
    }
    const candidates: Array<EventHubType | null | undefined> = [globalScope.window, globalScope, globalScope.document];
    for (const candidate of candidates) {
        if (!candidate) continue;
        const record = isObject(candidate) ? candidate : null;
        if (record && isFunction(record['addEventListener']) && isFunction(record['removeEventListener']) && isFunction(record['dispatchEvent'])) {
            eventHubRef = candidate;
            return eventHubRef;
        }
    }
    throw new Error('Global scope must provide event listener APIs');
};

const dispatchCustomEvent = <T>(type: string, detail: T): boolean => {
    const CustomEventCtor = getCustomEventCtor();
    const event = new CustomEventCtor(type, { detail });
    return getEventHub().dispatchEvent(event);
};

export { dispatchCustomEvent, getBody, getDocument, getDocumentElement, getElementByIdStrict, getEventHub, getGlobalScope, getHTMLElementCtor, getWindow, requireDocument };

export type { EventHubType, GlobalScopeType };
