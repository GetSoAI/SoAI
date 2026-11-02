/* SoAI - Explicit pane close targets and surviving native presentation selection [frontend/assets/ts/core/pagepanes/closing.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { queryNavigationProtection } from '@core/navigationGuards.ts';
import type { PagePaneWorkspace } from '@core/pagepanes/workspaceContracts.ts';
import { PagePaneUnavailableError } from '@core/pagepanes/placement.ts';
import type { RoutePane } from '@core/routing/router/RoutePane.ts';
import type { NavigationRequest } from '@core/routing/router/types.ts';
import { normalizeNavigationRequest } from '@core/routing/router/navigationRequest.ts';
import { shouldSkipNavigation } from '@core/routing/router/actions.ts';
import { preparePagePaneExit } from '@core/pagepanes/motion.ts';
import { throwIfAborted } from '@core/errors/abort.ts';

const preparePagePaneClose = async (root: HTMLElement, signal: AbortSignal): Promise<() => void> => {
    throwIfAborted(signal);
    if (root.hidden || !root.isConnected) return () => {};
    const release = await preparePagePaneExit(root, signal);
    if (signal.aborted) release();
    throwIfAborted(signal);
    return release;
};

const orderedPagePaneNeighbors = (workspace: PagePaneWorkspace, pane: RoutePane): readonly RoutePane[] => {
    const panes = workspace.getPanes();
    const index = panes.indexOf(pane);
    if (index < 0) throw new Error('Pane closing requires its allocated native owner');
    return [...panes.slice(0, index).reverse(), ...panes.slice(index + 1)];
};

const findPagePaneCloseNeighbor = (workspace: PagePaneWorkspace, pane: RoutePane): RoutePane | null => orderedPagePaneNeighbors(workspace, pane).find((candidate) => workspace.getPaneSlot(candidate).state === 'mounted' && candidate.currentRoute !== null && candidate.outlet.peekPageHost()?.getCurrentMountScope()?.admission.isActive() === true && shouldSkipNavigation(candidate.currentRoute, candidate.currentRoute, candidate.outlet)) ?? null;

const resolvePagePaneCloseRequest = (workspace: PagePaneWorkspace, pane: RoutePane): NavigationRequest => {
    if (workspace.getPaneSlot(pane).state === 'closing') throw new PagePaneUnavailableError('release-unconfirmed');
    const route = pane.currentRoute ?? pane.getRequestedRoute();
    if (!route) throw new PagePaneUnavailableError('no-eligible-slot');
    const neighbor = findPagePaneCloseNeighbor(workspace, pane);
    const parked = neighbor ? null : orderedPagePaneNeighbors(workspace, pane).find((candidate) => workspace.getPaneSlot(candidate).state === 'parked' && candidate.currentRoute !== null);
    if (!neighbor && !parked?.currentRoute) throw new PagePaneUnavailableError('no-eligible-slot');
    const owner = pane.outlet.peekPageHost()?.getCurrentMountScope();
    if (owner?.admission.isActive() && queryNavigationProtection(owner).explicitDestruction === 'blocked') throw new PagePaneUnavailableError('no-eligible-slot');
    if (parked?.currentRoute) {
        return normalizeNavigationRequest(parked.currentRoute, { pushState: false });
    }
    return normalizeNavigationRequest(route, { intent: 'close', pushState: false, presentation: pane.presentation.isFocused() ? 'user' : 'background' });
};

export { findPagePaneCloseNeighbor, preparePagePaneClose, resolvePagePaneCloseRequest };
