/* SoAI - Versioned pane history hints and opaque entry preservation [frontend/assets/ts/core/pagepanes/history.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasOwn, isPlainObject, isString } from '@core/typeGuards.ts';
import { isPagePaneIdentity } from '@core/pagepanes/contracts.ts';

interface PagePaneHistoryMetadata {
    readonly version: 1;
    readonly paneId: string;
}

interface PagePaneHistoryRecord {
    readonly route: string;
    readonly soaiPagePanes: PagePaneHistoryMetadata;
}

interface PagePaneHistoryHint {
    readonly type: 'absent' | 'matched' | 'mismatched' | 'incompatible' | 'opaque';
    readonly paneId: string | null;
}

interface PagePaneHistoryProjection<State> {
    readonly state: State | PagePaneHistoryRecord | (State & { route: string });
    readonly compatibility: 'supported' | 'incompatible' | 'opaque';
    readonly changed: boolean;
}

interface PagePaneHistoryEntry<State> {
    hint(route: string | null): PagePaneHistoryHint;
    project(route: string, paneId: string): PagePaneHistoryProjection<State>;
}

const readPagePaneHistoryHint = <State>(state: State, capturedRoute: string | null): PagePaneHistoryHint => {
    if (state === null) return { type: 'absent', paneId: null };
    if (state === undefined || !isPlainObject(state)) return { type: 'opaque', paneId: null };
    if (!hasOwn(state, 'soaiPagePanes') || !('soaiPagePanes' in state)) return { type: 'absent', paneId: null };
    const metadata = state.soaiPagePanes;
    if (!isPlainObject(metadata) || !hasOwn(metadata, 'version') || !('version' in metadata) || metadata.version !== 1 || !hasOwn(metadata, 'paneId') || !('paneId' in metadata) || !isPagePaneIdentity(metadata.paneId) || Object.keys(metadata).some((key) => key !== 'version' && key !== 'paneId')) return { type: 'incompatible', paneId: null };
    if (!hasOwn(state, 'route') || !('route' in state) || !isString(state.route) || state.route !== capturedRoute) return { type: 'mismatched', paneId: null };
    return { type: 'matched', paneId: metadata.paneId };
};

const createPagePaneHistoryState = (route: string, paneId: string): PagePaneHistoryRecord => {
    if (!route || !isPagePaneIdentity(paneId)) throw new Error('Pane history projection requires a route and bounded identity');
    return { route, soaiPagePanes: { version: 1, paneId } };
};

const projectPagePaneHistoryState = <State>(state: State, route: string, paneId: string): PagePaneHistoryProjection<State> => {
    const projection = createPagePaneHistoryState(route, paneId);
    if (state === null) return { state: projection, compatibility: 'supported', changed: true };
    if (state === undefined || !isPlainObject(state)) return { state, compatibility: 'opaque', changed: false };
    const hint = readPagePaneHistoryHint(state, 'route' in state && isString(state.route) ? state.route : null);
    if (hint.type === 'incompatible') return { state: { ...state, route }, compatibility: 'incompatible', changed: !hasOwn(state, 'route') || !('route' in state) || state.route !== route };
    const current = readPagePaneHistoryHint(state, route);
    return { state: { ...state, ...projection }, compatibility: 'supported', changed: current.type !== 'matched' || current.paneId !== paneId };
};

const capturePagePaneHistoryEntry = <State>(state: State): PagePaneHistoryEntry<State> => ({
    hint: (route) => readPagePaneHistoryHint(state, route),
    project: (route, paneId) => projectPagePaneHistoryState(state, route, paneId)
});

export { capturePagePaneHistoryEntry, createPagePaneHistoryState, projectPagePaneHistoryState, readPagePaneHistoryHint };
export type { PagePaneHistoryHint, PagePaneHistoryMetadata, PagePaneHistoryRecord, PagePaneHistoryProjection };
