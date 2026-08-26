/* SoAI - Metrics page layout controller [frontend/assets/ts/pages/metrics/controllers/page/metricsLayoutController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { MovablePanelLayoutController, type MovablePanelLayoutHost } from '@core/routing/pages/movablesections/panelLayoutController.ts';
import { createMetricsMovableLayoutConfig, createMetricsPanelBlueprints } from '@pages/metrics/rendering/layout/service.ts';
import type { MetricsPanelBlueprint, MetricsPanelId } from '@pages/metrics/rendering/layout/types.ts';
import type { MetricsPageSession } from '@pages/metrics/controllers/page/MetricsPageSession.ts';
import type { MetricsRuntimeOwners } from '@pages/metrics/controllers/page/contracts.ts';

interface MetricsLayoutPageHost extends MovablePanelLayoutHost {
    state: Pick<MetricsPageSession, 'storage'>;
    owners: Pick<MetricsRuntimeOwners, 'auth' | 'services'>;
}

class MetricsLayoutController {
    readonly #host: MetricsLayoutPageHost;
    readonly #panels: MovablePanelLayoutController<MetricsPanelId, MetricsPanelBlueprint>;

    constructor(host: MetricsLayoutPageHost) {
        this.#host = host;
        this.#panels = new MovablePanelLayoutController({
            host: this.#host,
            storage: {
                getLayout: (): JsonValue => this.#host.state.storage.get('metrics_layout', null) ?? null,
                saveLayout: (layout: JsonValue | undefined): void => this.#host.state.storage.set('metrics_layout', layout ?? null),
                getHiddenSectionIds: (): string[] => []
            },
            config: createMetricsMovableLayoutConfig(),
            contextId: 'metrics.layout',
            saveUnitId: 'metrics.layout',
            requestContextLabel: 'Metrics layout save',
            isCustomizationDisabled: () => this.#host.state.storage.getDashboardLocked()
        });
    }

    initialize(): void {
        this.#panels.load(createMetricsPanelBlueprints({ isAdmin: this.#host.owners.auth.isAdmin() }, { requestDistributionSourceIcon: this.#host.owners.services.getIconSync('request-distribution-source', { size: 14, strokeWidth: 1.8 }) }));
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
}

export { MetricsLayoutController };
export type { MetricsLayoutPageHost };
