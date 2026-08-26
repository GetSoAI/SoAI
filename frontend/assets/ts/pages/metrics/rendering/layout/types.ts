/* SoAI - Metrics page layout contracts [frontend/assets/ts/pages/metrics/rendering/layout/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { MovablePanelBlueprint } from '@core/routing/pages/movablesections/panelLayoutController.ts';

type MetricsPanelId = 'performance' | 'pluginHealth' | 'requestDistribution' | 'modelUsage' | 'apiKeyUsage' | 'systemPerformance' | 'frontendTelemetry';

type MetricsPanelBlueprint = MovablePanelBlueprint;

interface MetricsLayoutPermissions {
    isAdmin: boolean;
}

export type { MetricsLayoutPermissions, MetricsPanelBlueprint, MetricsPanelId };
