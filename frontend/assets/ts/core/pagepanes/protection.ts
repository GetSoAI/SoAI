/* SoAI - Workspace destruction protection and live component claim snapshots [frontend/assets/ts/core/pagepanes/protection.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { queryNavigationProtection, resolveNavigationDestructionOwner } from '@core/navigationGuards.ts';
import type { PagePaneSlot } from '@core/pagepanes/contracts.ts';
import type { PanePlacementSlot } from '@core/pagepanes/placement.ts';
import type { PageRouting } from '@core/routing/router/types.ts';
import type { RoutePane } from '@core/routing/router/RoutePane.ts';

interface PaneComponentReservation {
    readonly component: string;
    readonly opening: boolean;
}

const capturePanePlacement = (slots: Iterable<PagePaneSlot>, focused: RoutePane | null, requested: ReadonlyMap<string, PaneComponentReservation>, parseRoute: PageRouting['parseRoute'], authEpoch: number): readonly PanePlacementSlot[] =>
    [...slots].map((slot) => {
        const host = slot.pane.outlet.getPageHost();
        const ownership = host.getOwnership();
        const owner = resolveNavigationDestructionOwner(host.getCurrentMountScope(), authEpoch);
        const protection = queryNavigationProtection(owner);
        const route = slot.pane.currentRoute ? parseRoute(slot.pane.currentRoute)?.route : null;
        const committed = route?.component ?? null;
        if (slot.state === 'parked' && !committed) throw new Error('A parked pane requires its registered reconstruction route');
        const reservation = requested.get(slot.pane.id);
        return {
            ...ownership,
            id: slot.pane.id,
            components: committed ? [...new Set([...ownership.components, committed])] : ownership.components,
            requestedComponent: reservation?.component ?? null,
            state: slot.state === 'mounted' && reservation?.opening ? 'opening' : slot.state,
            visible: slot.pane.presentation.isVisible() && !slot.root.hidden,
            focused: focused === slot.pane,
            focusOrdinal: slot.focusOrdinal,
            destruction: protection.explicitDestruction,
            parkable: route?.reconstruction?.parking === 'clean' && ownership.currentComponent === committed && owner?.admission.isActive() === true && !protection.lossProtected && protection.isCurrent()
        };
    });

export { capturePanePlacement };
export type { PaneComponentReservation };
