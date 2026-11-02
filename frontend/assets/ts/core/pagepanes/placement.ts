/* SoAI - Pure workspace component identity and slot placement decisions [frontend/assets/ts/core/pagepanes/placement.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PaneCapacity } from '@core/pagepanes/capacity.ts';
import type { PageHostOwnership } from '@core/pagehost/types.ts';

interface PanePlacementSlot extends PageHostOwnership {
    readonly id: string;
    readonly state: 'mounted' | 'opening' | 'parked' | 'closing';
    readonly requestedComponent: string | null;
    readonly visible: boolean;
    readonly focused: boolean;
    readonly focusOrdinal: number;
    readonly destruction: 'admissible' | 'blocked';
    readonly parkable: boolean;
}

interface PanePlacementRequest {
    readonly originId: string;
    readonly component: string;
    readonly intent: 'navigate' | 'select' | 'split' | 'restore' | 'close';
    readonly exclusive: boolean;
    readonly originExclusive: boolean;
    readonly capacity: PaneCapacity | null;
}

type PanePlacementDecision = { readonly type: 'target'; readonly paneId: string; readonly source: 'origin' | 'owned' | 'replacement'; readonly capacityHint: boolean } | { readonly type: 'open'; readonly afterPaneId: string } | { readonly type: 'restore'; readonly paneId: string; readonly displaced: { readonly paneId: string; readonly action: 'park' | 'replace' } | null } | { readonly type: 'exclusive'; readonly paneId: string; readonly affectedPaneIds: readonly string[] } | { readonly type: 'unavailable'; readonly reason: 'capacity-unavailable' | 'release-unconfirmed' | 'no-eligible-slot' | 'restore-conflict' };

const selectLeastRecentlyFocused = (slots: readonly PanePlacementSlot[]): PanePlacementSlot | null => {
    let selected: PanePlacementSlot | null = null;
    for (const slot of slots) if (!selected || slot.focusOrdinal < selected.focusOrdinal) selected = slot;
    return selected;
};

const canReplaceSlot = (slot: PanePlacementSlot): boolean => slot.state !== 'closing' && slot.state !== 'opening' && slot.release === 'settled' && slot.destruction === 'admissible';

class PagePaneUnavailableError extends Error {
    readonly code = 'page_pane_unavailable';

    constructor(readonly reason: Extract<PanePlacementDecision, { readonly type: 'unavailable' }>['reason']) {
        super('Workspace pane placement is unavailable');
    }
}

const decidePanePlacement = (slots: readonly PanePlacementSlot[], request: PanePlacementRequest): PanePlacementDecision => {
    if (slots.length < 1 || slots.length > 3) throw new Error('Workspace placement requires one to three allocated slots');
    if (!request.component) throw new Error('Workspace placement requires a registered component');
    const identities = new Set<string>();
    const componentOwners = new Map<string, PanePlacementSlot>();
    for (const slot of slots) {
        if (!slot.id || identities.has(slot.id)) throw new Error('Workspace pane identities must be unique');
        if (!Number.isSafeInteger(slot.focusOrdinal) || slot.focusOrdinal < 0) throw new Error('Workspace focus ordinals must be non-negative safe integers');
        identities.add(slot.id);
        for (const component of [...slot.components, ...(slot.requestedComponent ? [slot.requestedComponent] : [])]) {
            if (!component) throw new Error('Workspace component claims must be non-empty');
            const existing = componentOwners.get(component);
            if (existing && existing !== slot) throw new Error('A workspace component cannot belong to multiple slots');
            componentOwners.set(component, slot);
        }
    }
    const origin = slots.find((slot) => slot.id === request.originId);
    if (!origin) throw new Error('Workspace navigation requires its allocated origin');
    if (request.intent === 'close') return origin.state === 'closing' || origin.release === 'failed' || origin.destruction === 'blocked' ? { type: 'unavailable', reason: 'release-unconfirmed' } : { type: 'target', paneId: origin.id, source: 'origin', capacityHint: false };
    const owned = componentOwners.get(request.component);
    if (owned && (owned.state === 'closing' || owned.release === 'failed' || (owned.currentComponent !== request.component && owned.requestedComponent !== request.component && owned.state !== 'parked' && owned.release !== 'pending'))) {
        return { type: 'unavailable', reason: 'release-unconfirmed' };
    }
    if (request.intent === 'restore') {
        if (request.exclusive || request.originExclusive) return { type: 'unavailable', reason: 'restore-conflict' };
        const target = owned ?? origin;
        if (target.release !== 'settled' || target.state === 'closing' || target.state === 'opening') return { type: 'unavailable', reason: 'release-unconfirmed' };
        if (target.currentComponent !== null && target.currentComponent !== request.component) return { type: 'unavailable', reason: 'restore-conflict' };
        if (target.currentComponent === request.component || target.visible || (request.capacity !== null && slots.filter((slot) => slot.visible).length < request.capacity)) return { type: 'target', paneId: target.id, source: owned ? 'owned' : 'origin', capacityHint: false };
        return { type: 'unavailable', reason: 'capacity-unavailable' };
    }
    if (request.exclusive) {
        if (slots.some((slot) => slot.release !== 'settled' || slot.state === 'closing' || slot.destruction === 'blocked')) return { type: 'unavailable', reason: 'release-unconfirmed' };
        return { type: 'exclusive', paneId: owned?.id ?? origin.id, affectedPaneIds: slots.map((slot) => slot.id) };
    }
    if (owned) {
        if (owned.state !== 'parked') return { type: 'target', paneId: owned.id, source: 'owned', capacityHint: false };
        if (request.capacity === null) return { type: 'unavailable', reason: 'capacity-unavailable' };
        const visible = slots.filter((slot) => slot.visible);
        if (visible.length < request.capacity) return { type: 'restore', paneId: owned.id, displaced: null };
        const parkable = selectLeastRecentlyFocused(visible.filter((slot) => !slot.focused && slot.parkable && canReplaceSlot(slot)));
        if (parkable) return { type: 'restore', paneId: owned.id, displaced: { paneId: parkable.id, action: 'park' } };
        const victim = selectLeastRecentlyFocused(visible.filter(canReplaceSlot));
        return victim ? { type: 'restore', paneId: owned.id, displaced: { paneId: victim.id, action: 'replace' } } : { type: 'unavailable', reason: 'no-eligible-slot' };
    }
    if (request.intent === 'navigate' || request.intent === 'select' || request.capacity === 1 || request.originExclusive) {
        if (origin.state === 'closing' || origin.release === 'failed' || origin.destruction === 'blocked') return { type: 'unavailable', reason: 'release-unconfirmed' };
        return { type: 'target', paneId: origin.id, source: 'origin', capacityHint: request.intent === 'split' && request.capacity === 1 && !request.originExclusive };
    }
    if (request.capacity === null) return { type: 'unavailable', reason: 'capacity-unavailable' };
    const visible = slots.filter((slot) => slot.visible);
    if (visible.length < request.capacity && slots.length < 3) return { type: 'open', afterPaneId: origin.id };
    const replaceVisible = visible.length >= request.capacity;
    const victim = selectLeastRecentlyFocused(slots.filter((slot) => slot.id !== origin.id && slot.visible === replaceVisible && canReplaceSlot(slot)));
    return victim ? { type: 'target', paneId: victim.id, source: 'replacement', capacityHint: false } : { type: 'unavailable', reason: 'no-eligible-slot' };
};

export { decidePanePlacement, PagePaneUnavailableError };
export type { PanePlacementDecision, PanePlacementRequest, PanePlacementSlot };
