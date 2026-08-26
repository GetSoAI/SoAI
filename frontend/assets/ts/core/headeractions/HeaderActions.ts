/* SoAI - Frontend header action ownership [frontend/assets/ts/core/headeractions/HeaderActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { HEADER_ACTION_IDS } from '@core/headeractions/constants.ts';
import { cloneRenderable, createActionSnapshot, createBaseDefinition, deriveRenderable, normalizeActionId, normalizeContextPayload, renderableChanged } from '@core/headeractions/state.ts';

import type { ActionDefinition, ActionSnapshot, ContextPayload, DefinitionInput, PayloadInput, RegistryEntry, Renderable, SubscriberCallback } from '@core/headeractions/types.ts';
import { ensureError } from '@core/errors/coerce.ts';

const normalizeContextId = (value: string): string | null => {
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : null;
};

const shouldRetainContextRemoval = (previous: Renderable | null, next: Renderable): boolean => previous?.visible === true && next.visible === false;

const retainRenderableForHandoff = (renderable: Renderable): Renderable => ({
    ...renderable,
    onClick: null
});

const suppressDetachForLayoutEdit = (snapshot: ActionSnapshot, layoutEditActive: boolean): ActionSnapshot => {
    if (!layoutEditActive) {
        return snapshot;
    }
    return {
        actions: snapshot.actions.map((action) => (action.id === HEADER_ACTION_IDS.detach ? { ...action, visible: false, onClick: null } : action))
    };
};

class HeaderActions {
    #registry: Map<string, RegistryEntry> = new Map();
    #subscribers: Set<SubscriberCallback> = new Set();
    #actionHandoffs: Set<string> = new Set();
    #layoutEditContexts: Set<string> = new Set();

    #ensureEntry(id: string): RegistryEntry {
        const normalized = normalizeActionId(id);
        if (!this.#registry.has(normalized)) {
            this.#registry.set(normalized, {
                id: normalized,
                definition: createBaseDefinition({ id: normalized }),
                contexts: new Map<string, ContextPayload>(),
                renderable: null
            });
        }
        const entry = this.#registry.get(normalized);
        if (!entry) {
            throw new Error('Failed to create header action registry entry');
        }
        return entry;
    }

    #emitSnapshot(): void {
        if (this.#subscribers.size === 0) {
            return;
        }
        const snapshot = this.#createSnapshot();
        this.#subscribers.forEach((listener) => {
            try {
                listener(snapshot);
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.warn('HeaderActions', 'Header action subscriber failed', runtimeError);
            }
        });
    }

    #refreshEntry(entry: RegistryEntry): boolean {
        const nextRenderable = deriveRenderable(entry);
        if (!renderableChanged(entry.renderable, nextRenderable)) {
            return false;
        }
        entry.renderable = nextRenderable;
        return true;
    }

    #retainContextRemoval(entry: RegistryEntry, previousRenderable: Renderable | null, nextRenderable: Renderable): boolean {
        if (!previousRenderable || !this.#actionHandoffs.has(entry.id) || !shouldRetainContextRemoval(previousRenderable, nextRenderable)) {
            return false;
        }
        const retainedRenderable = retainRenderableForHandoff(previousRenderable);
        const changed = renderableChanged(entry.renderable, retainedRenderable);
        entry.renderable = retainedRenderable;
        if (changed) {
            this.#emitSnapshot();
        }
        return true;
    }

    defineAction(id: string, definition: DefinitionInput = {}): Renderable | null {
        const entry = this.#ensureEntry(id);
        entry.definition = {
            ...entry.definition,
            ...createBaseDefinition({ ...definition, id: entry.id })
        };
        if (typeof definition.onClick === 'function') {
            entry.definition.onClick = definition.onClick;
        }
        const changed = this.#refreshEntry(entry);
        if (changed) {
            this.#emitSnapshot();
        }
        return cloneRenderable(entry.renderable);
    }

    setActionState(id: string, contextId: string, payload: PayloadInput = {}): Renderable | null {
        const entry = this.#ensureEntry(id);
        const contextKey = normalizeContextId(contextId) ?? entry.id;
        const contextPayload = normalizeContextPayload(payload);
        entry.contexts.set(contextKey, contextPayload);
        const changed = this.#refreshEntry(entry);
        if (changed) {
            this.#emitSnapshot();
        }
        return cloneRenderable(entry.renderable);
    }

    removeActionContext(id: string, contextId: string): boolean {
        const entry = this.#ensureEntry(id);
        const contextKey = normalizeContextId(contextId) ?? entry.id;
        const contextPayload = entry.contexts.get(contextKey);
        if (!contextPayload) {
            return false;
        }
        const previousRenderable = entry.renderable;
        entry.contexts.delete(contextKey);
        const nextRenderable = deriveRenderable(entry);
        if (this.#retainContextRemoval(entry, previousRenderable, nextRenderable)) {
            return true;
        }
        const changed = this.#refreshEntry(entry);
        if (changed) {
            this.#emitSnapshot();
        }
        return true;
    }

    #createSnapshot(): ActionSnapshot {
        return suppressDetachForLayoutEdit(createActionSnapshot(this.#registry), this.#layoutEditContexts.size > 0);
    }

    clearAction(id: string): boolean {
        const normalized = normalizeContextId(id);
        if (!normalized || !this.#registry.has(normalized)) {
            return false;
        }
        this.#actionHandoffs.delete(normalized);
        this.#registry.delete(normalized);
        this.#emitSnapshot();
        return true;
    }

    resetActionState(id: string): boolean {
        const normalized = normalizeContextId(id);
        if (!normalized || !this.#registry.has(normalized)) {
            return false;
        }
        const entry = this.#registry.get(normalized);
        if (!entry) {
            return false;
        }
        entry.contexts.clear();
        const changed = this.#refreshEntry(entry);
        if (changed) {
            this.#emitSnapshot();
        }
        return true;
    }

    startActionHandoff(id: string): void {
        const normalized = normalizeContextId(id);
        if (normalized) {
            this.#actionHandoffs.add(normalized);
        }
    }

    endActionHandoff(id: string): void {
        const normalized = normalizeContextId(id);
        if (!normalized || !this.#actionHandoffs.delete(normalized)) {
            return;
        }
        const entry = this.#registry.get(normalized);
        if (!entry) {
            return;
        }
        const changed = this.#refreshEntry(entry);
        if (changed) {
            this.#emitSnapshot();
        }
    }

    setLayoutEditActive(contextId: string, active: boolean): void {
        const normalized = normalizeContextId(contextId);
        if (!normalized) {
            return;
        }
        const hadContext = this.#layoutEditContexts.has(normalized);
        if (active) {
            this.#layoutEditContexts.add(normalized);
        } else {
            this.#layoutEditContexts.delete(normalized);
        }
        if (hadContext !== active) {
            this.#emitSnapshot();
        }
    }

    subscribe(listener: SubscriberCallback): () => void {
        this.#subscribers.add(listener);
        listener(this.#createSnapshot());
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
    if (!headerActionsInstance) {
        headerActionsInstance = new HeaderActions();
    }
    return headerActionsInstance;
};

export { HeaderActions, getHeaderActions };
export type { ActionDefinition, ActionSnapshot, ContextPayload, DefinitionInput, PayloadInput, Renderable, SubscriberCallback };
