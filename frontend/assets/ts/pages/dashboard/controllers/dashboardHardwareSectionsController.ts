/* SoAI - Dashboard page hardware sections controller [frontend/assets/ts/pages/dashboard/controllers/dashboardHardwareSectionsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DashboardHardwareSectionsControllerDependencies, DashboardHardwareSectionsRenderContext } from '@pages/dashboard/controllers/contracts.ts';
import { destroyHardwareWidgetsManager, renderHardwareWidgetsSection } from '@pages/dashboard/controllers/hardwareWidgetsEffects.ts';
import { renderNetworkInterfacesSection } from '@pages/dashboard/controllers/mappers.ts';
import { createDashboardHardwareWidgetsManagerState, type DashboardHardwareWidgetsManagerState } from '@pages/dashboard/controllers/state.ts';
import { renderStorageSection } from '@pages/dashboard/controllers/view.ts';

class DashboardHardwareSectionsController {
    readonly #host: DashboardHardwareSectionsControllerDependencies['host'];
    readonly #state: DashboardHardwareSectionsControllerDependencies['state'];
    readonly #isDestroyed: DashboardHardwareSectionsControllerDependencies['isDestroyed'];
    readonly #widgets: DashboardHardwareWidgetsManagerState;

    constructor(dependencies: DashboardHardwareSectionsControllerDependencies) {
        this.#host = dependencies.host;
        this.#state = dependencies.state;
        this.#isDestroyed = dependencies.isDestroyed;
        this.#widgets = createDashboardHardwareWidgetsManagerState();
    }

    destroy(): void {
        destroyHardwareWidgetsManager(this.#widgets);
    }

    renderNetworkInterfacesSection(): void {
        renderNetworkInterfacesSection(this.#createRenderContext());
    }

    renderStorageSection(): void {
        renderStorageSection(this.#createRenderContext());
    }

    async renderHardwareWidgetsSection(): Promise<void> {
        await renderHardwareWidgetsSection(this.#createHardwareWidgetsRenderContext());
    }

    #createRenderContext(): DashboardHardwareSectionsRenderContext {
        return {
            host: this.#host,
            state: this.#state,
            isDestroyed: this.#isDestroyed
        };
    }

    #createHardwareWidgetsRenderContext(): DashboardHardwareSectionsRenderContext & {
        widgets: DashboardHardwareWidgetsManagerState;
    } {
        return {
            ...this.#createRenderContext(),
            widgets: this.#widgets
        };
    }
}

export { DashboardHardwareSectionsController };
export type { DashboardHardwareSectionsControllerDependencies };
