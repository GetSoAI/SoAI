/* SoAI - Dashboard page state model [frontend/assets/ts/pages/dashboard/state/dashboardStateModel.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

interface DashboardState {
    metrics: JsonObject;
    plugins: readonly JsonValue[];
    models: readonly JsonValue[];
}

const pickString = (...candidates: JsonValue[]): string => {
    for (const candidate of candidates) {
        if (isString(candidate) && candidate.trim()) {
            return candidate.trim();
        }
    }
    return '';
};

const createInitialDashboardState = (): DashboardState => ({
    metrics: {},
    plugins: [],
    models: []
});

export { createInitialDashboardState, pickString };
export type { DashboardState };
