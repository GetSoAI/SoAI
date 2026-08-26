/* SoAI - Frontend hardware page persistence contract [frontend/assets/ts/features/hardware/pageStorage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';

interface HardwarePageStorage {
    get: (key: string, defaultValue: JsonObject) => JsonObject;
    set: (key: string, value: JsonObject) => void;
}

export type { HardwarePageStorage };
