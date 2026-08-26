/* SoAI - Shared frontend stream types [frontend/assets/ts/core/streamTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

export type UnsubscribeFunction = (() => void) | null;

export type ResourceListener<T = JsonValue | null | undefined> = (snapshot: T) => void;

export interface ResourceWaiter<T = JsonValue | null | undefined> {
    resolve?: (value: T) => void;
    reject?: (error: Error) => void;
}

export interface CapabilityManifestState {
    data: JsonObject | null;
    error: Error | null;
}

export interface SubscribeOptions {
    immediate?: boolean;
    emitCurrent?: boolean;
    ensureStart?: boolean;
}
