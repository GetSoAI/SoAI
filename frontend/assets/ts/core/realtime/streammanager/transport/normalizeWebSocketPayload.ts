/* SoAI - Shared realtime normalize WebSocket payload [frontend/assets/ts/core/realtime/streammanager/transport/normalizeWebSocketPayload.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

const normalizeWebSocketPayload = (payload: JsonValue | null | undefined): JsonObject | null => {
    return isJsonObject(payload) ? payload : null;
};

export { normalizeWebSocketPayload };
