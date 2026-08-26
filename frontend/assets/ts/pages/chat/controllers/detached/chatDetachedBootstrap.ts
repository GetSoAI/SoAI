/* SoAI - Chat page detached bootstrap [frontend/assets/ts/pages/chat/controllers/detached/chatDetachedBootstrap.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { optionalTrimmedString, readBooleanOrTrueStringValue } from '@core/types/payloadValueReaders.ts';
import { isString } from '@core/typeGuards.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { NormalizedDetachedParameters } from '@pages/chat/types.ts';

const optionalRawDraftMessage = (value: JsonValue): string | null => {
    return isString(value) && value.length > 0 ? value : null;
};

const readDetachedParameters = (value: JsonValue): JsonObject | null => {
    if (!isJsonObject(value)) {
        return null;
    }
    return Object.fromEntries(Object.entries(value));
};

export const normalizeDetachedBootstrapParameters = (raw: JsonObject = {}): NormalizedDetachedParameters => {
    return {
        conversationId: optionalTrimmedString(raw['conversationId']),
        modelId: optionalTrimmedString(raw['model_id']),
        sidebarOpen: readBooleanOrTrueStringValue(raw['sidebarOpen']),
        textZoom: raw['text_zoom'] === undefined ? null : Number(raw['text_zoom']),
        searchQuery: optionalTrimmedString(raw['searchQuery']),
        parameters: readDetachedParameters(raw['parameters'] ?? null),
        widescreenMode: readBooleanOrTrueStringValue(raw['widescreen_mode'] ?? null),
        draftMessage: optionalRawDraftMessage(raw['draftMessage'] ?? null)
    };
};
