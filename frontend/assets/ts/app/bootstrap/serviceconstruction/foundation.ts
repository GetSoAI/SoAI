/* SoAI - Frontend application foundation [frontend/assets/ts/app/bootstrap/serviceconstruction/foundation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ApiClient } from '@core/api/service.ts';
import { createSystemLimitsService } from '@core/api/systemLimitsService.ts';
import { createBranding } from '@core/branding/public.ts';
import { ComponentRegistry, ComponentSupport } from '@core/componentsupport/public.ts';
import { createEventBus } from '@core/EventBus.ts';
import { createLicenseService } from '@core/licenseservice/service.ts';
import { createLogValidation } from '@core/logvalidation/public.ts';
import { createMainStatusMonitor } from '@core/mainstatusmonitor/public.ts';
import { createMaintenanceCoordinator } from '@core/maintenanceCoordinator.ts';
import { createPageRegistry } from '@core/pageRegistry.ts';
import { getCleanupManager } from '@core/resources.ts';
import { createLayoutRuntimeManager } from '@core/runtime/LayoutManager.ts';
import { createStateManager } from '@core/state/public.ts';
import { createIconService } from '@core/ui/icons/iconservice/public.ts';
import { requireFrontendEditionComposition } from '@app/edition/frontendEditionComposition.ts';

interface BootstrapFoundationServices {
    apiClient: ApiClient;
    stateManager: ReturnType<typeof createStateManager>;
    licenseService: ReturnType<typeof createLicenseService>;
    mainStatusMonitor: ReturnType<typeof createMainStatusMonitor>;
    cleanupManager: ReturnType<typeof getCleanupManager>;
    globalEventBus: ReturnType<typeof createEventBus>;
    layoutRuntime: ReturnType<typeof createLayoutRuntimeManager>;
    pageRegistry: ReturnType<typeof createPageRegistry>;
    maintenanceCoordinator: ReturnType<typeof createMaintenanceCoordinator>;
    branding: ReturnType<typeof createBranding>;
    componentRegistry: ComponentRegistry;
    componentSupport: ComponentSupport;
    iconService: ReturnType<typeof createIconService>;
    logValidation: ReturnType<typeof createLogValidation>;
    systemLimitsService: ReturnType<typeof createSystemLimitsService>;
}

const createBootstrapFoundationServices = (): BootstrapFoundationServices => {
    const componentRegistry = new ComponentRegistry();
    const logValidation = createLogValidation();
    const edition = requireFrontendEditionComposition();
    return {
        apiClient: new ApiClient(edition.createHostManagementApi),
        stateManager: createStateManager(),
        licenseService: createLicenseService(),
        mainStatusMonitor: createMainStatusMonitor(),
        cleanupManager: getCleanupManager(),
        globalEventBus: createEventBus(),
        layoutRuntime: createLayoutRuntimeManager(),
        pageRegistry: createPageRegistry(),
        maintenanceCoordinator: createMaintenanceCoordinator(),
        branding: createBranding(edition.branding),
        componentRegistry,
        componentSupport: new ComponentSupport(componentRegistry),
        iconService: createIconService(),
        logValidation,
        systemLimitsService: createSystemLimitsService()
    };
};

export { createBootstrapFoundationServices };
