/* SoAI - Metrics advanced modal host registry [frontend/assets/ts/features/metrics/modals/advancedMetricsHost.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';

interface MetricsAdvancedModalHost {
    getMetricsSnapshot: () => JsonValue | null;
    getTelemetryStatusSnapshot: () => JsonValue | null;
}

let activeHost: MetricsAdvancedModalHost | null = null;

const setActiveMetricsAdvancedModalHost = (host: MetricsAdvancedModalHost | null): void => {
    activeHost = host;
};

const requireActiveMetricsHost = (): MetricsAdvancedModalHost => {
    if (!activeHost) {
        throw new Error('Metrics advanced modal host is not registered');
    }
    return activeHost;
};

export { requireActiveMetricsHost, setActiveMetricsAdvancedModalHost };
export type { MetricsAdvancedModalHost };
