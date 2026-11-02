/* SoAI - Native reconstruction candidate completion and redirect retirement [frontend/assets/ts/core/pagepanes/reconstruction.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PagePaneWorkspace } from '@core/pagepanes/workspaceContracts.ts';
import type { RoutePane } from '@core/routing/router/RoutePane.ts';
import { PagePaneUnavailableError } from '@core/pagepanes/placement.ts';

interface PagePaneReconstruction {
    readonly workspace: PagePaneWorkspace;
    readonly pane: RoutePane;
    readonly route: string;
    requireCurrent(): void;
    captureCancellation(cancel: (() => void) | null): void;
}

const releasePagePaneCandidate = async (workspace: PagePaneWorkspace, pane: RoutePane): Promise<void> => {
    if (workspace.getPanes().includes(pane)) {
        await workspace.removePane(pane);
        await workspace.whenPaneReleased(pane);
        return;
    }
    pane.disposeNavigation();
    if (pane.outlet.destroy) await pane.outlet.destroy();
    else await pane.outlet.destroyCurrent({ force: true });
    await pane.outlet.whenReleased();
};

const reconstructPagePane = async ({ workspace, pane, route, requireCurrent, captureCancellation }: PagePaneReconstruction): Promise<'mounted' | 'removed'> => {
    try {
        const navigation = pane.routing.navigate(route, { intent: 'restore', pushState: false });
        captureCancellation(pane.captureCancellation('layout-reconstruction-superseded'));
        await navigation;
        requireCurrent();
        if (pane.outlet.peekPageHost()?.getCurrent()) return 'mounted';
        await releasePagePaneCandidate(workspace, pane);
        return 'removed';
    } catch (error) {
        requireCurrent();
        if (error instanceof PagePaneUnavailableError && error.reason === 'restore-conflict') await releasePagePaneCandidate(workspace, pane);
        throw error;
    } finally {
        captureCancellation(null);
    }
};

export { reconstructPagePane, releasePagePaneCandidate };
