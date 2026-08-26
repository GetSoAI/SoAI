/* SoAI - Hardware page layout controller [frontend/assets/ts/pages/hardware/controllers/page/hardwareLayoutController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { MovablePanelLayoutController, type MovablePanelLayoutHost } from '@core/routing/pages/movablesections/panelLayoutController.ts';
import { createHardwareMovableLayoutConfig, createHardwarePanelBlueprints } from '@pages/hardware/rendering/layout/service.ts';
import { ensureHardwareWebuiPermissions } from '@pages/hardware/controllers/realtime/permissionsController.ts';
import type { HardwarePanelBlueprint, HardwarePanelId } from '@pages/hardware/rendering/layout/types.ts';
import type { HardwarePageState } from '@pages/hardware/state/state.ts';
import type { ModuleLoggerFunctionValue } from '@pages/hardware/types.ts';

interface HardwareLayoutPageHost extends MovablePanelLayoutHost {
    state: HardwarePageState;
    storage: HardwareLayoutStorage;
    logger: ModuleLoggerFunctionValue;
    isDetached(): boolean;
}

interface HardwareLayoutStorage {
    get(key: string, defaultValue?: JsonValue): JsonValue;
    set(key: string, value: JsonValue): void;
    getDashboardLocked(): boolean;
}

class HardwareLayoutController {
    readonly #host: HardwareLayoutPageHost;
    readonly #panels: MovablePanelLayoutController<HardwarePanelId, HardwarePanelBlueprint>;

    constructor(host: HardwareLayoutPageHost) {
        this.#host = host;
        this.#panels = new MovablePanelLayoutController({
            host: this.#host,
            storage: {
                getLayout: (): JsonValue => this.#host.storage.get('hardware_layout', null),
                saveLayout: (layout: JsonValue | undefined): void => this.#host.storage.set('hardware_layout', layout ?? null),
                getHiddenSectionIds: (): string[] => []
            },
            config: createHardwareMovableLayoutConfig(),
            contextId: 'hardware.layout',
            saveUnitId: 'hardware.layout',
            requestContextLabel: 'Hardware layout save',
            isCustomizationDisabled: () => this.#host.isDetached() || this.#host.storage.getDashboardLocked()
        });
    }

    async initialize(): Promise<void> {
        await this.#ensurePermissions();
        const actions = new Set(this.#host.state.webuiPermissions?.actions ?? []);
        this.#panels.load(
            createHardwarePanelBlueprints({
                canTuneGpu: actions.has('HW_GPU_TUNING'),
                canViewProcesses: actions.has('HW_PROCESS_VIEW')
            })
        );
    }

    hasPanel(panelId: HardwarePanelId): boolean {
        return this.#panels.hasPanel(panelId);
    }

    hasChanges(): boolean {
        return this.#panels.hasChanges();
    }

    onResponsiveLayout(): void {
        this.#panels.onResponsiveLayout();
    }

    destroy(): void {
        this.#panels.destroy();
    }

    async #ensurePermissions(): Promise<void> {
        await ensureHardwareWebuiPermissions({ state: this.#host.state, logger: this.#host.logger });
    }
}

export { HardwareLayoutController };
export type { HardwareLayoutPageHost, HardwareLayoutStorage };
