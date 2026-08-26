/* SoAI - Shared frontend header action bus [frontend/assets/ts/core/headerActionBus.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dispatchCustomEvent } from '@core/environment/public.ts';
import { isObject } from '@core/typeGuards.ts';
import type { DefinitionInput, PayloadInput } from '@core/headeractions/types.ts';

interface HeaderActionEvents {
    define: string;
    update: string;
    remove: string;
}

interface DefinePayload {
    actionId: string;
    definition: DefinitionInput;
}

interface UpdatePayload {
    actionId: string;
    contextId: string;
    state: PayloadInput;
}

interface RemovePayload {
    actionId: string;
    contextId: string;
}

interface HeaderActionControllerOptions {
    actionId: string;
    contextId?: string;
    definition?: DefinitionInput;
    initialState?: PayloadInput;
}

interface HeaderActionController {
    define: (definitionPayload?: DefinitionInput) => void;
    update: (statePayload?: PayloadInput) => void;
    show: (statePayload?: PayloadInput) => void;
    hide: () => void;
    clear: () => void;
    dispose: () => void;
}

const HEADER_ACTION_EVENTS: HeaderActionEvents = Object.freeze({
    define: 'soai:header:action:define',
    update: 'soai:header:action:update',
    remove: 'soai:header:action:remove'
});

const ensureActionId = (value: string): string => {
    const trimmed = value.trim();
    if (!trimmed) {
        throw new Error('Header action id must not be empty');
    }
    return trimmed;
};

const ensureContextId = (actionId: string, contextId: string | undefined): string => {
    if (contextId) {
        const trimmed = contextId.trim();
        if (trimmed) {
            return trimmed;
        }
    }
    return actionId;
};

type HeaderActionEventPayload = DefinePayload | UpdatePayload | RemovePayload;

const dispatchHeaderEvent = (type: string, detail: HeaderActionEventPayload): void => {
    dispatchCustomEvent(type, detail);
};

const defineHeaderAction = (actionId: string, definition: DefinitionInput = {}): string => {
    const id = ensureActionId(actionId);
    const payload: DefinePayload = {
        actionId: id,
        definition: { ...definition }
    };
    dispatchHeaderEvent(HEADER_ACTION_EVENTS.define, payload);
    return id;
};

const updateHeaderAction = (actionId: string, contextId: string, state: PayloadInput = {}): string => {
    const id = ensureActionId(actionId);
    if (!isObject(state)) {
        throw new Error('Header action state must be an object');
    }
    const context = ensureContextId(id, contextId);
    const payload: UpdatePayload = {
        actionId: id,
        contextId: context,
        state: { ...state }
    };
    dispatchHeaderEvent(HEADER_ACTION_EVENTS.update, payload);
    return id;
};

const removeHeaderAction = (actionId: string, contextId: string): string => {
    const id = ensureActionId(actionId);
    const context = ensureContextId(id, contextId);
    const payload: RemovePayload = {
        actionId: id,
        contextId: context
    };
    dispatchHeaderEvent(HEADER_ACTION_EVENTS.remove, payload);
    return id;
};

const createHeaderActionController = (options: HeaderActionControllerOptions = { actionId: '' }): HeaderActionController => {
    const id = ensureActionId(options.actionId);
    const context = ensureContextId(id, options.contextId);
    const definition = options.definition;
    if (isObject(definition)) {
        defineHeaderAction(id, definition);
    }
    if (isObject(options.initialState)) {
        updateHeaderAction(id, context, options.initialState);
    }
    let disposed = false;
    return {
        define(definitionPayload: DefinitionInput = {}): void {
            if (disposed) {
                throw new Error(`Header action controller for ${id} has been disposed`);
            }
            if (isObject(definitionPayload)) {
                defineHeaderAction(id, definitionPayload);
            }
        },
        update(statePayload: PayloadInput = {}): void {
            if (disposed) {
                throw new Error(`Header action controller for ${id} has been disposed`);
            }
            updateHeaderAction(id, context, statePayload);
        },
        show(statePayload: PayloadInput = {}): void {
            if (disposed) {
                throw new Error(`Header action controller for ${id} has been disposed`);
            }
            updateHeaderAction(id, context, { ...statePayload, visible: true });
        },
        hide(): void {
            if (disposed) {
                return;
            }
            removeHeaderAction(id, context);
        },
        clear(): void {
            if (disposed) {
                return;
            }
            removeHeaderAction(id, context);
        },
        dispose(): void {
            if (disposed) {
                return;
            }
            removeHeaderAction(id, context);
            disposed = true;
        }
    };
};

export { HEADER_ACTION_EVENTS, createHeaderActionController, defineHeaderAction, updateHeaderAction, removeHeaderAction };

export type { HeaderActionController, HeaderActionControllerOptions };
