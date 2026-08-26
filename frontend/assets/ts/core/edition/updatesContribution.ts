/* SoAI - Trusted product update contribution contracts [frontend/assets/ts/core/edition/updatesContribution.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { OsEndpoints } from '@core/api/endpoints/osEndpointContracts.ts';
import type { PageContext } from '@core/pagecontext/public.ts';
import type { PageResources } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedback } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { PageServices } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageUi } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { PageStreaming } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { StateManager } from '@core/state/StateManager.ts';
import type { StorageService } from '@core/storage/StorageService.ts';

interface UpdatesOperationOutcome {
    type: 'skipped' | 'noUpdates' | 'updatesFound' | 'error';
    message: string;
    updatesCount: number;
}

interface UpdatesInstallOutcome {
    type: 'skipped' | 'started' | 'completed' | 'error';
    message: string;
}

interface UpdatesProductRenderDependencies {
    getIconSync: PageServices['getIconSync'];
}

interface UpdatesProductRuntimeDependencies {
    api: OsEndpoints;
    storage: StorageService;
    pageResources: PageResources;
    feedback: PageFeedback;
    pageElements: PageUi;
    pageDom: PageDom;
    pageContext: PageContext;
    services: PageServices;
    stateManager: StateManager;
    streaming: PageStreaming;
    onInstallStarted(): number;
    onInstallCompleted(outcome: UpdatesInstallOutcome, operationRevision: number): void;
}

interface UpdatesProductController {
    initialize(): Promise<void>;
    checkUpdates(): Promise<UpdatesOperationOutcome>;
    handleAction(action: string, actionElement: HTMLElement): Promise<void> | void;
    destroy(): void;
}

interface UpdatesEditionContribution {
    readonly stats: readonly { id: string; label: string }[];
    render(dependencies: UpdatesProductRenderDependencies): TrustedHtml;
    isAction(value: string | undefined): value is string;
    createController(dependencies: UpdatesProductRuntimeDependencies): UpdatesProductController;
}

export type { UpdatesEditionContribution, UpdatesInstallOutcome, UpdatesOperationOutcome, UpdatesProductController, UpdatesProductRenderDependencies, UpdatesProductRuntimeDependencies };
