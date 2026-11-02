/* SoAI - Shared frontend header action bus [frontend/assets/ts/core/headerActionBus.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getEventHub } from '@core/environment/public.ts';
import { getHeaderActions } from '@core/headeractions/public.ts';
import { isPresentationOwnerActive, isPresentationOwnerCurrent } from '@core/presentationOwner.ts';
import type { DefinitionInput, HeaderActionRegistration, PayloadInput } from '@core/headeractions/types.ts';
import type { GlobalPresentationOwner, PresentationOwner } from '@core/routing/router/types.ts';

interface HeaderActionControllerOptions<Owner extends PresentationOwner = PresentationOwner> {
    actionId: string;
    readonly owner: Owner;
    contextId?: string;
    definition?: DefinitionInput;
    initialState?: PayloadInput;
}

interface HeaderActionController<Owner extends PresentationOwner = PresentationOwner> {
    readonly registration: HeaderActionRegistration<Owner>;
    define: (definitionPayload?: DefinitionInput) => void;
    update: (statePayload?: PayloadInput) => void;
    show: (statePayload?: PayloadInput) => void;
    hide: () => void;
    clear: () => void;
    dispose: () => void;
}

const HEADER_ACTION_EVENTS = Object.freeze({ define: 'soai:header:action:define', update: 'soai:header:action:update', remove: 'soai:header:action:remove' });

type HeaderActionEventDetail = { type: 'define'; actionId: string; owner: GlobalPresentationOwner; definition: DefinitionInput } | { type: 'update'; actionId: string; contextId: string; registration: HeaderActionRegistration; state: PayloadInput } | { type: 'remove'; actionId: string; contextId: string; registration: HeaderActionRegistration };

class HeaderActionEvent extends CustomEvent<HeaderActionEventDetail> {
    constructor(detail: HeaderActionEventDetail) {
        super(HEADER_ACTION_EVENTS[detail.type], { detail });
    }
}

const ensureActionId = (value: string): string => {
    const trimmed = value.trim();
    if (!trimmed) throw new Error('Header action id must not be empty');
    return trimmed;
};

const defineHeaderAction = (actionId: string, owner: GlobalPresentationOwner, definition: DefinitionInput = {}): string => {
    const id = ensureActionId(actionId);
    getEventHub().dispatchEvent(new HeaderActionEvent({ type: 'define', actionId: id, owner, definition: { ...definition } }));
    return id;
};

const updateHeaderAction = (actionId: string, contextId: string, registration: HeaderActionRegistration, state: PayloadInput = {}): string => {
    const id = ensureActionId(actionId);
    const context = contextId.trim() || id;
    getEventHub().dispatchEvent(new HeaderActionEvent({ type: 'update', actionId: id, contextId: context, registration, state: { ...state } }));
    return id;
};

const removeHeaderAction = (actionId: string, contextId: string, registration: HeaderActionRegistration): string => {
    const id = ensureActionId(actionId);
    const context = contextId.trim() || id;
    getEventHub().dispatchEvent(new HeaderActionEvent({ type: 'remove', actionId: id, contextId: context, registration }));
    return id;
};

const createHeaderActionController = <Owner extends PresentationOwner>(options: HeaderActionControllerOptions<Owner>): HeaderActionController<Owner> => {
    const id = ensureActionId(options.actionId);
    const context = options.contextId?.trim() || id;
    const owner = options.owner;
    const registration = getHeaderActions().createRegistration(owner);
    let state: PayloadInput | null = options.initialState ? { ...options.initialState } : null;
    let disposed = false;
    let published = false;
    let unsubscribe: (() => void) | null = null;
    const define = (definition: DefinitionInput = {}): void => {
        if (disposed) throw new Error(`Header action controller for ${id} has been disposed`);
        if (owner.type !== 'global') throw new Error('Header action definitions require document ownership');
        defineHeaderAction(id, owner, definition);
    };
    const synchronize = (): void => {
        if (disposed) return;
        if (!isPresentationOwnerCurrent(owner)) {
            dispose();
            return;
        }
        if (!isPresentationOwnerActive(owner)) return;
        if (state && !published) {
            published = true;
            updateHeaderAction(id, context, registration, state);
        } else getHeaderActions().refreshOwner(owner);
    };
    const update = (payload: PayloadInput = {}): void => {
        if (disposed) throw new Error(`Header action controller for ${id} has been disposed`);
        state = { ...payload };
        published = false;
        synchronize();
    };
    const hide = (): void => {
        if (!disposed) update({ visible: false });
    };
    const dispose = (): void => {
        if (disposed) return;
        disposed = true;
        const release = unsubscribe;
        unsubscribe = null;
        try {
            release?.();
        } finally {
            removeHeaderAction(id, context, registration);
        }
    };
    try {
        if (options.definition) define(options.definition);
        if (owner.type !== 'global') {
            const release = owner.presentation.subscribe(synchronize);
            if (disposed) release();
            else unsubscribe = release;
        }
        synchronize();
    } catch (error) {
        dispose();
        throw error;
    }
    return { registration, define, update, show: (payload = {}) => update({ ...payload, visible: true }), hide, clear: hide, dispose };
};

export { HeaderActionEvent, HEADER_ACTION_EVENTS, createHeaderActionController, defineHeaderAction, updateHeaderAction, removeHeaderAction };
export type { HeaderActionController, HeaderActionControllerOptions };
