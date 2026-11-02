/* SoAI - Bounded native pane resource release and retained ownership outcomes [frontend/assets/ts/core/pagepanes/retirement.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RoutePane } from '@core/routing/router/RoutePane.ts';
import type { PageMountScope } from '@core/routing/router/types.ts';
import type { PagePaneWorkspace } from '@core/pagepanes/workspaceContracts.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import { runCleanupStepCollectingFailure, runAsyncCleanupStepCollectingFailure, throwCollectedCleanupFailures } from '@core/lifecycle/cleanup.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { claimErrorReporting } from '@core/errors/reportingOwnership.ts';
import { errorHandler } from '@core/errorHandler.ts';

interface PagePaneRetirement {
    readonly pane: RoutePane;
    readonly owner: PageMountScope | null;
    readonly action: 'park' | 'remove';
}

interface PagePaneRetirementDependencies {
    readonly workspace: PagePaneWorkspace;
    readonly modalPresenter: Pick<ModalPresenterApi, 'closeAll'>;
    readonly authEpoch: number;
    readonly readAuthEpoch: () => number;
    readonly releaseSeals: (pane: RoutePane) => void;
}

type PagePaneRetirementOutcome = { readonly type: 'released' } | { readonly type: 'degraded'; readonly failures: readonly { readonly paneId: string; readonly error: Error }[] };

const releasePagePaneResources = async (retirements: readonly PagePaneRetirement[], dependencies: PagePaneRetirementDependencies): Promise<PagePaneRetirementOutcome> => {
    const { workspace, modalPresenter, authEpoch, readAuthEpoch, releaseSeals } = dependencies;
    const outcomes = await Promise.allSettled(
        retirements.map(async ({ pane, owner, action }) => {
            const failures: Error[] = [];
            if (owner) runCleanupStepCollectingFailure(() => modalPresenter.closeAll(owner, { reason: 'pane-retirement', force: true, restoreFocus: false }), failures);
            await runAsyncCleanupStepCollectingFailure(async () => {
                if (action === 'park') {
                    const wait = pane.outlet.destroyCurrent({ force: true });
                    void pane.outlet
                        .whenReleased()
                        .then(() => {
                            if (readAuthEpoch() === authEpoch && workspace.getPanes().includes(pane)) workspace.parkReleasedPane(pane);
                            releaseSeals(pane);
                        })
                        .catch((error) => {
                            const failure = ensureError(error);
                            if (claimErrorReporting(failure)) errorHandler.warn('PagePaneAdmission', 'Parked pane resource release remains unconfirmed', failure);
                        });
                    await wait;
                    return;
                }
                const wait = workspace.removePane(pane);
                void workspace.whenPaneReleased(pane)?.then(
                    () => releaseSeals(pane),
                    () => {}
                );
                await wait;
            }, failures);
            throwCollectedCleanupFailures(failures);
        })
    );
    const failures = outcomes.flatMap((outcome, index) => {
        if (outcome.status === 'fulfilled') return [];
        const retirement = retirements[index];
        if (!retirement) throw new Error('A pane release outcome lost its captured owner');
        return [{ paneId: retirement.pane.id, error: ensureError(outcome.reason) }];
    });
    return failures.length ? { type: 'degraded', failures } : { type: 'released' };
};

export { releasePagePaneResources };
export type { PagePaneRetirement, PagePaneRetirementOutcome };
