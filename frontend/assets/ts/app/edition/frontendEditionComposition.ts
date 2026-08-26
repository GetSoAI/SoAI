/* SoAI - Immutable frontend edition composition [frontend/assets/ts/app/edition/frontendEditionComposition.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PageOptions, PageRegistry } from '@core/pageRegistry.ts';
import type { ModalDefinition } from '@core/modals/modalPresenter.ts';
import type { RawRouteDefinition } from '@core/routeregistry/contracts.ts';
import type { BasePageDependencies } from '@core/routing/pages/pagetypes/public.ts';
import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import type { OsEndpoints } from '@core/api/endpoints/osEndpointContracts.ts';
import type { DashboardEditionContribution } from '@core/edition/dashboardContribution.ts';
import { configureLicensingEditionContribution, type LicensingEditionContribution } from '@core/edition/licensingContribution.ts';
import type { SettingsEditionContribution } from '@core/edition/settingsContribution.ts';
import type { UpdatesEditionContribution } from '@core/edition/updatesContribution.ts';
import type { BrandingDescriptor } from '@core/branding/types.ts';
import type { DashboardIntroProductContribution } from '@features/firstrunmodals/dashboardIntroProduct.ts';
import type { SoaiOsCapabilitiesService } from '@core/soaiOsAccess.ts';
import { configureRouteContributions } from '@core/routeregistry/state.ts';
import { configureEditionTaskCatalog, type EditionTaskCatalog } from '@core/tasks/editionTaskCatalog.ts';
import { configureExpectedBackendEdition } from '@core/edition/backendEditionIntegrity.ts';

type RegisteredPageClass = Parameters<PageRegistry['register']>[1];

interface FrontendPageContribution {
    readonly id: string;
    readonly pageClass: RegisteredPageClass;
    readonly options: (basePageDependencies: BasePageDependencies) => Partial<PageOptions>;
}

interface FrontendEditionComposition {
    readonly edition: 'soai-core' | 'soai-os';
    readonly routes: readonly RawRouteDefinition[];
    readonly pages: readonly FrontendPageContribution[];
    readonly modalDefinitions: readonly ModalDefinition[];
    readonly createHostManagementApi: (api: ApiClientContext) => OsEndpoints | null;
    readonly settings: SettingsEditionContribution | null;
    readonly licensing: LicensingEditionContribution;
    readonly dashboard: DashboardEditionContribution | null;
    readonly updates: UpdatesEditionContribution | null;
    readonly userSyncSections: readonly string[];
    readonly services: readonly string[];
    readonly translationCatalogs: readonly string[];
    readonly taskCatalog: EditionTaskCatalog;
    readonly branding: BrandingDescriptor;
    readonly createDashboardIntro: (api: OsEndpoints | null, capabilities: Pick<SoaiOsCapabilitiesService, 'getSnapshot'>) => DashboardIntroProductContribution | null;
}

let selectedComposition: FrontendEditionComposition | null = null;

const selectFrontendEditionComposition = (composition: FrontendEditionComposition): void => {
    if (selectedComposition !== null) {
        throw new Error('Frontend edition composition is already selected');
    }
    selectedComposition = Object.freeze(composition);
    configureExpectedBackendEdition(composition.edition);
    configureLicensingEditionContribution(composition.licensing);
    configureRouteContributions(composition.routes);
    configureEditionTaskCatalog(composition.taskCatalog);
};

const requireFrontendEditionComposition = (): FrontendEditionComposition => {
    if (selectedComposition === null) {
        throw new Error('Frontend edition composition must be selected before bootstrap');
    }
    return selectedComposition;
};

export { requireFrontendEditionComposition, selectFrontendEditionComposition };
export type { FrontendEditionComposition, FrontendPageContribution };
