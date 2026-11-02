/* SoAI - Versioned committed pane layout validation and restore precedence [frontend/assets/ts/core/pagepanes/persistence.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SoaiEdition } from '@core/edition/backendEditionIntegrity.ts';
import { isPagePaneIdentity, PAGE_PANE_ROUTE_LIMIT, type PagePaneSlot } from '@core/pagepanes/contracts.ts';
import { projectReconstructionRoute } from '@core/routeregistry/reconstruction.ts';
import { normalizeNavigationRequest } from '@core/routing/router/navigationRequest.ts';
import type { PageRouting } from '@core/routing/router/types.ts';
import { hasOwn, isFiniteInteger, isString } from '@core/typeGuards.ts';
import { isJsonArray, isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

interface PagePaneLayoutIdentity {
    readonly accountId: string;
    readonly windowId: string;
    readonly edition: SoaiEdition;
}

interface PagePaneLayoutEntry extends JsonObject {
    readonly id: string;
    readonly route: string;
}

interface PagePaneLayoutRecord extends JsonObject, PagePaneLayoutIdentity {
    readonly version: 1;
    readonly panes: readonly PagePaneLayoutEntry[];
    readonly focusedPaneId: string;
    readonly parkedPaneIds: readonly string[];
}

type PagePaneLayoutDecode = { readonly type: 'valid'; readonly record: PagePaneLayoutRecord } | { readonly type: 'invalid'; readonly reason: 'shape' | 'identity' | 'route' | 'component' | 'placement' } | { readonly type: 'incompatible' | 'foreign' };

type PagePaneLayoutOwnership = { readonly type: 'current'; readonly value: JsonObject } | { readonly type: 'invalid'; readonly reason: 'shape' | 'identity' } | { readonly type: 'incompatible' | 'foreign' };

type PagePaneRestoreDecision = { readonly type: 'ordinary'; readonly route: string | null } | { readonly type: 'restore'; readonly record: PagePaneLayoutRecord; readonly primary: PagePaneLayoutEntry };

type PagePaneLayoutCapture = { readonly type: 'record'; readonly record: PagePaneLayoutRecord } | { readonly type: 'unavailable'; readonly reason: 'route-limit' | 'not-reconstructible' | 'placement' };

const LAYOUT_RECORD_KEYS: readonly string[] = Object.freeze(['version', 'accountId', 'windowId', 'edition', 'panes', 'focusedPaneId', 'parkedPaneIds']);

const inspectPagePaneLayoutOwnership = (value: JsonValue, identity: PagePaneLayoutIdentity): PagePaneLayoutOwnership => {
    if (!isJsonObject(value)) return { type: 'invalid', reason: 'shape' };
    if (value['version'] !== 1) return isFiniteInteger(value['version']) && value['version'] > 1 ? { type: 'incompatible' } : { type: 'invalid', reason: 'shape' };
    const accountId = value['accountId'];
    const windowId = value['windowId'];
    const edition = value['edition'];
    if (!isString(accountId) || !accountId || !isPagePaneIdentity(windowId) || !isString(edition) || !edition) return { type: 'invalid', reason: 'identity' };
    if (accountId !== identity.accountId || windowId !== identity.windowId || edition !== identity.edition) return { type: 'foreign' };
    return { type: 'current', value };
};

const decodePagePaneLayout = (input: JsonValue, identity: PagePaneLayoutIdentity, parseRoute: PageRouting['parseRoute']): PagePaneLayoutDecode => {
    const ownership = inspectPagePaneLayoutOwnership(input, identity);
    if (ownership.type !== 'current') return ownership;
    const value = ownership.value;
    if (Object.keys(value).length !== LAYOUT_RECORD_KEYS.length || LAYOUT_RECORD_KEYS.some((key) => !hasOwn(value, key))) return { type: 'invalid', reason: 'shape' };
    const storedPanes = value['panes'];
    const focusedPaneId = value['focusedPaneId'];
    const parkedPaneIds = value['parkedPaneIds'];
    if (!isJsonArray(storedPanes) || storedPanes.length < 1 || storedPanes.length > 3 || !isPagePaneIdentity(focusedPaneId) || !isJsonArray(parkedPaneIds)) return { type: 'invalid', reason: 'placement' };
    const identities = new Set<string>();
    const components = new Set<string>();
    const panes: PagePaneLayoutEntry[] = [];
    for (const candidate of storedPanes) {
        if (!isJsonObject(candidate) || Object.keys(candidate).length !== 2 || !hasOwn(candidate, 'id') || !hasOwn(candidate, 'route')) return { type: 'invalid', reason: 'shape' };
        const id = candidate['id'];
        const route = candidate['route'];
        if (!isPagePaneIdentity(id) || identities.has(id)) return { type: 'invalid', reason: 'placement' };
        if (!isString(route) || !route || route.length > PAGE_PANE_ROUTE_LIMIT) return { type: 'invalid', reason: 'route' };
        try {
            if (normalizeNavigationRequest(route).path !== route) return { type: 'invalid', reason: 'route' };
            const parsed = parseRoute(route);
            if (!parsed || projectReconstructionRoute(route, parsed.route) !== route) return { type: 'invalid', reason: 'route' };
            if (components.has(parsed.route.component)) return { type: 'invalid', reason: 'component' };
            components.add(parsed.route.component);
        } catch {
            return { type: 'invalid', reason: 'route' };
        }
        identities.add(id);
        panes.push(Object.freeze({ id, route }));
    }
    if (!identities.has(focusedPaneId)) return { type: 'invalid', reason: 'placement' };
    const parked = new Set<string>();
    for (const parkedId of parkedPaneIds) {
        if (!isPagePaneIdentity(parkedId) || !identities.has(parkedId) || parked.has(parkedId) || parkedId === focusedPaneId) return { type: 'invalid', reason: 'placement' };
        parked.add(parkedId);
    }
    return { type: 'valid', record: Object.freeze({ version: 1, accountId: identity.accountId, windowId: identity.windowId, edition: identity.edition, panes: Object.freeze(panes), focusedPaneId, parkedPaneIds: Object.freeze([...parked]) }) };
};

const decidePagePaneRestore = (record: PagePaneLayoutRecord | null, incomingRoute: string | null): PagePaneRestoreDecision => {
    if (!record) return { type: 'ordinary', route: incomingRoute };
    const primary = record.panes.find((entry) => entry.id === record.focusedPaneId);
    if (!primary) throw new Error('A validated pane layout requires its focused entry');
    if (incomingRoute && incomingRoute !== primary.route) return { type: 'ordinary', route: incomingRoute };
    return { type: 'restore', record, primary };
};

const capturePagePaneLayout = (slots: Iterable<PagePaneSlot>, focusedPaneId: string | null, identity: PagePaneLayoutIdentity, parseRoute: PageRouting['parseRoute']): PagePaneLayoutCapture => {
    const entries = [...slots].filter((slot) => slot.state !== 'closing').map((slot) => ({ id: slot.pane.id, route: slot.pane.currentRoute, parked: slot.state === 'parked', parkedOrdinal: slot.parkedOrdinal }));
    const panes: PagePaneLayoutEntry[] = [];
    const parkedPaneIds = entries
        .filter((entry) => entry.parked)
        .sort((left, right) => left.parkedOrdinal - right.parkedOrdinal)
        .map((entry) => entry.id);
    for (const entry of entries) {
        if (!entry.route) continue;
        let parsed: ReturnType<PageRouting['parseRoute']>;
        try {
            parsed = parseRoute(entry.route);
        } catch {
            return { type: 'unavailable', reason: 'not-reconstructible' };
        }
        const route = parsed ? projectReconstructionRoute(entry.route, parsed.route) : null;
        if (!route) return { type: 'unavailable', reason: 'not-reconstructible' };
        if (route.length > PAGE_PANE_ROUTE_LIMIT) return { type: 'unavailable', reason: 'route-limit' };
        panes.push({ id: entry.id, route });
    }
    if (!focusedPaneId || !panes.some((entry) => entry.id === focusedPaneId)) return { type: 'unavailable', reason: 'placement' };
    const decoded = decodePagePaneLayout({ version: 1, accountId: identity.accountId, windowId: identity.windowId, edition: identity.edition, panes, focusedPaneId, parkedPaneIds }, identity, parseRoute);
    if (decoded.type !== 'valid') return { type: 'unavailable', reason: 'placement' };
    return { type: 'record', record: decoded.record };
};

export { decodePagePaneLayout, decidePagePaneRestore, capturePagePaneLayout, inspectPagePaneLayoutOwnership };
export type { PagePaneLayoutIdentity, PagePaneLayoutEntry, PagePaneLayoutRecord, PagePaneLayoutDecode, PagePaneRestoreDecision, PagePaneLayoutCapture };
