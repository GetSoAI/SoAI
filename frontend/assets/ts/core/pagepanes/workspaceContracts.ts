/* SoAI - Native workspace coordination contracts [frontend/assets/ts/core/pagepanes/workspaceContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RoutePane } from '@core/routing/router/RoutePane.ts';
import type { PageRouting } from '@core/routing/router/types.ts';
import type { PagePaneSlot } from '@core/pagepanes/contracts.ts';
import type { PaneCapacity } from '@core/pagepanes/capacity.ts';
import type { PanePlacementSlot } from '@core/pagepanes/placement.ts';
import type { PaneComponentReservation } from '@core/pagepanes/protection.ts';
import type { PagePanePersistence } from '@core/pagepanes/session.ts';
import type { ResourceTracker } from '@core/resourcetracker/service.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';

interface PagePaneWorkspace {
    readonly persistence: PagePanePersistence;
    getFocusedPane(): RoutePane | null;
    getPanes(): readonly RoutePane[];
    getPaneSlot(pane: RoutePane): Readonly<PagePaneSlot>;
    getCapacity(): PaneCapacity | null;
    claimFocusIntent(): number;
    isCurrentFocusIntent(intent: number): boolean;
    focusIfCurrent(pane: RoutePane, intent: number): boolean;
    capturePlacement(requested: ReadonlyMap<string, PaneComponentReservation>, parseRoute: PageRouting['parseRoute'], authEpoch: number): readonly PanePlacementSlot[];
    blockPaneInput(pane: RoutePane): () => void;
    retirePanes(panes: readonly RoutePane[], successor?: RoutePane | null): void;
    insertPaneAfter(pane: RoutePane, after: RoutePane | null): Promise<void>;
    removePane(pane: RoutePane): Promise<void>;
    whenPaneReleased(pane: RoutePane): Promise<void> | null;
    parkReleasedPane(pane: RoutePane, parkedOrdinal?: number | null): void;
    subscribeLayout(listener: () => void): () => void;
    subscribeFocusIntent(listener: (intent: number) => void): () => void;
    reveal(pane: RoutePane): void;
}

interface PagePaneAdmissionDependencies {
    readonly workspace: PagePaneWorkspace;
    readonly createPane: (id?: string) => RoutePane;
    readonly parseRoute: PageRouting['parseRoute'];
    readonly readAuthEpoch: () => number;
    readonly modalPresenter: Pick<ModalPresenterApi, 'hasOpenModals' | 'closeAll'>;
    readonly resources: ResourceTracker;
}

export type { PagePaneWorkspace, PagePaneAdmissionDependencies };
