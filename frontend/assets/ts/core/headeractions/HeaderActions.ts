/* SoAI - Frontend header action ownership [frontend/assets/ts/core/headeractions/HeaderActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { HEADER_ACTION_IDS } from '@core/headeractions/constants.ts';
import { cloneRenderable, createActionSnapshot, createBaseDefinition, deriveRenderable, normalizeActionId, normalizeContextPayload, renderableChanged } from '@core/headeractions/state.ts';
import { isPresentationOwnerActive, isPresentationOwnerFocused } from '@core/presentationOwner.ts';
import type { PageMountPresentation } from '@core/routing/router/types.ts';
import type { ActionDefinition, ActionSnapshot, ContextPayload, DefinitionInput, GlobalPresentationOwner, HeaderActionHandoff, HeaderActionRegistration, PayloadInput, PresentationOwner, RegistryEntry, Renderable, SubscriberCallback } from '@core/headeractions/types.ts';
import { ensureError } from '@core/errors/coerce.ts';

class HeaderActions {
    #snapshotRevision = 0;
    #registrationSequence = new SequenceToken();
    #registrationOrdinals = new WeakMap<HeaderActionRegistration, number>();
    #registry = new Map<string, RegistryEntry>();
    #subscribers = new Set<SubscriberCallback>();
    #retiredRegistrations = new WeakSet<HeaderActionRegistration>();
    #actionHandoffs = new Map<string, Map<PresentationOwner, HeaderActionHandoff>>();
    #layoutEditContexts = new Map<PresentationOwner, Map<string, HeaderActionRegistration>>();

    #ensureEntry(id: string): RegistryEntry {
        const normalized = normalizeActionId(id);
        let entry = this.#registry.get(normalized);
        if (!entry) {
            entry = { id: normalized, definition: createBaseDefinition({ id: normalized }), contexts: new Map(), renderable: null };
            this.#registry.set(normalized, entry);
        }
        return entry;
    }

    #emitSnapshot(): void {
        const revision = ++this.#snapshotRevision;
        if (!this.#subscribers.size) return;
        const snapshot = this.#createSnapshot();
        for (const listener of [...this.#subscribers]) {
            if (revision !== this.#snapshotRevision) break;
            if (!this.#subscribers.has(listener)) continue;
            try {
                listener(snapshot);
            } catch (error) {
                errorHandler.warn('HeaderActions', 'Header action subscriber failed', ensureError(error));
            }
        }
    }

    #refreshEntry(entry: RegistryEntry): boolean {
        const nextRenderable = deriveRenderable(entry, this.#actionHandoffs.get(entry.id)?.values());
        if (!renderableChanged(entry.renderable, nextRenderable)) return false;
        entry.renderable = nextRenderable;
        return true;
    }

    defineAction(id: string, owner: GlobalPresentationOwner, definition: DefinitionInput = {}): Renderable | null {
        if (owner.type !== 'global') throw new Error('Header action definitions require document ownership');
        const entry = this.#ensureEntry(id);
        entry.definition = { ...entry.definition, ...createBaseDefinition({ ...definition, id: entry.id }) };
        if (typeof definition.onClick === 'function') entry.definition.onClick = definition.onClick;
        if (this.#refreshEntry(entry)) this.#emitSnapshot();
        return cloneRenderable(entry.renderable);
    }

    createRegistration<Owner extends PresentationOwner>(owner: Owner): HeaderActionRegistration<Owner> {
        const registration = Object.freeze({ owner, token: Symbol(owner.ownerId) });
        this.#registrationOrdinals.set(registration, this.#registrationSequence.next());
        return registration;
    }

    setActionState(id: string, contextId: string, registration: HeaderActionRegistration, payload: PayloadInput = {}): Renderable | null {
        const owner = registration.owner;
        const ordinal = this.#registrationOrdinals.get(registration);
        if (ordinal === undefined || this.#retiredRegistrations.has(registration) || !isPresentationOwnerActive(owner)) return null;
        const entry = this.#ensureEntry(id);
        const contextKey = contextId.trim() || entry.id;
        const contexts = entry.contexts.get(owner) ?? new Map<string, ContextPayload>();
        const previous = contexts.get(contextKey);
        if (previous && (this.#registrationOrdinals.get(previous.registration) ?? 0) > ordinal) return null;
        if (previous && previous.registration !== registration) this.#retiredRegistrations.add(previous.registration);
        const contextPayload = normalizeContextPayload(registration, payload);
        const onClick = contextPayload.onClick;
        if (onClick) {
            contextPayload.onClick = (event) => {
                if (entry.contexts.get(owner)?.get(contextKey) !== contextPayload || !isPresentationOwnerActive(owner) || !isPresentationOwnerFocused(owner)) return;
                onClick(event);
            };
        }
        contexts.set(contextKey, contextPayload);
        entry.contexts.set(owner, contexts);
        if (this.#refreshEntry(entry)) this.#emitSnapshot();
        return cloneRenderable(entry.renderable);
    }

    removeActionContext(id: string, contextId: string, registration: HeaderActionRegistration): boolean {
        this.#retiredRegistrations.add(registration);
        const entry = this.#registry.get(normalizeActionId(id));
        const contexts = entry?.contexts.get(registration.owner);
        const contextKey = contextId.trim() || id;
        if (!entry || contexts?.get(contextKey)?.registration !== registration) return false;
        contexts.delete(contextKey);
        if (!contexts.size) entry.contexts.delete(registration.owner);
        if (this.#refreshEntry(entry)) this.#emitSnapshot();
        return true;
    }

    refreshOwner(owner: PresentationOwner): void {
        let changed = false;
        for (const entry of this.#registry.values()) {
            if (entry.contexts.has(owner) || this.#actionHandoffs.get(entry.id)?.has(owner)) changed = this.#refreshEntry(entry) || changed;
        }
        if (changed || this.#layoutEditContexts.has(owner)) this.#emitSnapshot();
    }

    #createSnapshot(): ActionSnapshot {
        const snapshot = createActionSnapshot(this.#registry);
        const editing = [...this.#layoutEditContexts.keys()].some((owner) => isPresentationOwnerActive(owner) && isPresentationOwnerFocused(owner));
        if (!editing) return snapshot;
        return { actions: snapshot.actions.map((action) => (action.id === HEADER_ACTION_IDS.detach ? { ...action, visible: false, onClick: null } : action)) };
    }

    clearAction(id: string, owner: GlobalPresentationOwner): boolean {
        if (owner.type !== 'global') throw new Error('Clearing header definitions requires document ownership');
        const normalized = normalizeActionId(id);
        const entry = this.#registry.get(normalized);
        if (!entry) return false;
        for (const contexts of entry.contexts.values()) for (const context of contexts.values()) this.#retiredRegistrations.add(context.registration);
        this.#actionHandoffs.delete(normalized);
        this.#registry.delete(normalized);
        this.#emitSnapshot();
        return true;
    }

    resetActionState(id: string, owner: PresentationOwner): boolean {
        const entry = this.#registry.get(normalizeActionId(id));
        const contexts = entry?.contexts.get(owner);
        if (!entry || !contexts) return false;
        for (const context of contexts.values()) this.#retiredRegistrations.add(context.registration);
        entry.contexts.delete(owner);
        if (this.#refreshEntry(entry)) this.#emitSnapshot();
        return true;
    }

    startActionHandoff(id: string, owner: PresentationOwner, presentation: PageMountPresentation): () => void {
        const normalized = normalizeActionId(id);
        const entry = this.#registry.get(normalized);
        const contexts = entry?.contexts.get(owner);
        const renderable = entry && contexts ? deriveRenderable({ ...entry, contexts: new Map([[owner, contexts]]) }) : null;
        const handoff: HeaderActionHandoff = { owner, presentation, renderable };
        const handoffs = this.#actionHandoffs.get(normalized) ?? new Map<PresentationOwner, HeaderActionHandoff>();
        const previousHandoff = handoffs.get(owner);
        handoffs.set(owner, handoff);
        this.#actionHandoffs.set(normalized, handoffs);
        const refresh = (): void => {
            if (handoffs.get(owner) === handoff && entry && this.#refreshEntry(entry)) this.#emitSnapshot();
        };
        let unsubscribe: () => void;
        try {
            unsubscribe = presentation.subscribe(refresh);
        } catch (error) {
            if (handoffs.get(owner) === handoff) {
                if (previousHandoff) handoffs.set(owner, previousHandoff);
                else handoffs.delete(owner);
            }
            if (!handoffs.size && this.#actionHandoffs.get(normalized) === handoffs) this.#actionHandoffs.delete(normalized);
            throw error;
        }
        let released = false;
        return () => {
            if (released) return;
            released = true;
            if (handoffs.get(owner) === handoff) handoffs.delete(owner);
            if (!handoffs.size && this.#actionHandoffs.get(normalized) === handoffs) this.#actionHandoffs.delete(normalized);
            try {
                unsubscribe();
            } finally {
                if (entry && this.#refreshEntry(entry)) this.#emitSnapshot();
            }
        };
    }

    setLayoutEditActive(contextId: string, registration: HeaderActionRegistration, active: boolean): void {
        const owner = registration.owner;
        const contexts = this.#layoutEditContexts.get(owner) ?? new Map<string, HeaderActionRegistration>();
        if (active) {
            const ordinal = this.#registrationOrdinals.get(registration);
            if (ordinal === undefined || this.#retiredRegistrations.has(registration) || !isPresentationOwnerActive(owner)) return;
            const previous = contexts.get(contextId);
            if (previous && (this.#registrationOrdinals.get(previous) ?? 0) > ordinal) return;
            if (previous && previous !== registration) this.#retiredRegistrations.add(previous);
            contexts.set(contextId, registration);
            this.#layoutEditContexts.set(owner, contexts);
        } else {
            if (contexts.get(contextId) !== registration) return;
            contexts.delete(contextId);
            if (!contexts.size) this.#layoutEditContexts.delete(owner);
        }
        this.#emitSnapshot();
    }

    subscribe(listener: SubscriberCallback): () => void {
        this.#subscribers.add(listener);
        try {
            listener(this.#createSnapshot());
        } catch (error) {
            this.#subscribers.delete(listener);
            throw error;
        }
        return () => {
            this.#subscribers.delete(listener);
        };
    }

    get snapshot(): ActionSnapshot {
        return this.#createSnapshot();
    }
}

let headerActionsInstance: HeaderActions | null = null;
const getHeaderActions = (): HeaderActions => {
    if (!headerActionsInstance) headerActionsInstance = new HeaderActions();
    return headerActionsInstance;
};

export { HeaderActions, getHeaderActions };
export type { ActionDefinition, ActionSnapshot, ContextPayload, DefinitionInput, PayloadInput, Renderable, SubscriberCallback };
