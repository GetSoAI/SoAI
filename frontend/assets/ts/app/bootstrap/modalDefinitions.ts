/* SoAI - App modal definitions registration [frontend/assets/ts/app/bootstrap/modalDefinitions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import type { WebuiUserEndpoints } from '@core/api/endpoints/webuiUserEndpoints.ts';
import type { FirstRunStateStorage } from '@core/firstrun/protocols.ts';
import type { ModalDefinition } from '@core/modals/modalPresenter.ts';
import { FOLDER_PICKER_MODAL_DEFINITIONS } from '@core/fileexplorerbrowser/folderPickerModal.ts';
import { LICENSE_MODAL_DEFINITIONS } from '@core/licenseservice/modalDefinitions.ts';
import { DIALOGS_MODAL_DEFINITIONS } from '@core/ui/modals/dialogs/modalDefinitions.ts';
import { CONTENT_PREVIEW_MODAL_DEFINITIONS } from '@core/ui/modals/contentpreview/modalDefinitions.ts';
import { ABOUT_MODAL_DEFINITIONS } from '@features/about/modals/easterEggModal.ts';
import { createChatModalDefinitions } from '@features/chat/modals/modalDefinitions.ts';
import { createDashboardIntroModalDefinition, type DashboardIntroDriverPresenceState, type DashboardIntroStreamManager } from '@features/firstrunmodals/public.ts';
import { EXPORT_PREVIEW_MODAL_DEFINITIONS } from '@features/exportpreview/public.ts';
import { METRICS_MODAL_DEFINITIONS } from '@features/metrics/modals/advancedMetricsModal.ts';
import { AUTOMATION_MODAL_DEFINITIONS } from '@features/automation/modals/modalDefinitions.ts';
import { FILE_EXPLORER_MODAL_DEFINITIONS } from '@features/fileexplorer/modals/modalDefinitions.ts';
import { SETTINGS_MODAL_DEFINITIONS } from '@features/settings/modals/modalDefinitions.ts';
import { MODEL_DETAIL_MODAL_DEFINITIONS } from '@features/modeldetail/modals/modalDefinitions.ts';
import { PROMPTS_MODAL_DEFINITIONS } from '@features/prompts/modals/modalDefinitions.ts';
import { createPluginsModalDefinitions } from '@features/plugins/modals/modalDefinitions.ts';
import { MODELS_MODAL_DEFINITIONS } from '@features/models/modals/modalDefinitions.ts';
import { HARDWARE_MODAL_DEFINITIONS } from '@features/hardware/modals/modalDefinitions.ts';
import { requireFrontendEditionComposition } from '@app/edition/frontendEditionComposition.ts';
import type { DashboardIntroProductContribution } from '@features/firstrunmodals/dashboardIntroProduct.ts';

const getAppModalDefinitions = (dependencies: { storage: FirstRunStateStorage; apiClient: ApiClientContext & { webui?: Pick<WebuiUserEndpoints, 'memory'> | undefined }; dashboardIntroDriverPresence: DashboardIntroDriverPresenceState; dashboardIntroProduct: DashboardIntroProductContribution | null; streamManager: DashboardIntroStreamManager }): readonly ModalDefinition[] => {
    return [
        ...DIALOGS_MODAL_DEFINITIONS,
        ...LICENSE_MODAL_DEFINITIONS,
        ...CONTENT_PREVIEW_MODAL_DEFINITIONS,
        ...EXPORT_PREVIEW_MODAL_DEFINITIONS,
        createDashboardIntroModalDefinition({
            storage: dependencies.storage,
            driverPresence: dependencies.dashboardIntroDriverPresence,
            product: dependencies.dashboardIntroProduct,
            streamManager: dependencies.streamManager
        }),
        ...createChatModalDefinitions({ storage: dependencies.storage, apiClient: dependencies.apiClient }),
        ...METRICS_MODAL_DEFINITIONS,
        ...AUTOMATION_MODAL_DEFINITIONS,
        ...FILE_EXPLORER_MODAL_DEFINITIONS,
        ...requireFrontendEditionComposition().modalDefinitions,
        ...SETTINGS_MODAL_DEFINITIONS,
        ...MODEL_DETAIL_MODAL_DEFINITIONS,
        ...MODELS_MODAL_DEFINITIONS,
        ...PROMPTS_MODAL_DEFINITIONS,
        ...createPluginsModalDefinitions({ storage: dependencies.storage }),
        ...HARDWARE_MODAL_DEFINITIONS,
        ...FOLDER_PICKER_MODAL_DEFINITIONS,
        ...ABOUT_MODAL_DEFINITIONS
    ];
};

export { getAppModalDefinitions };
