/* SoAI - Model detail page control layer mapping [frontend/assets/ts/pages/modeldetail/controllers/page/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { unwrap } from '@core/realtime/streammanager/resources/normalizers.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isObject } from '@core/typeGuards.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import { isModelEntryMatch } from '@pages/modeldetail/contracts/modelDetailPageSupport.ts';

const extractModelDetailPayload = (modelId: string | null, raw: JsonValue | null | undefined): ModelRecord | null => {
    if (!modelId) {
        return null;
    }
    const unwrapped = unwrap(raw ?? null);
    if (isObject(unwrapped) && isObject(unwrapped['model'])) {
        return unwrapped['model'];
    }
    if (isObject(unwrapped) && (unwrapped['universalId'] || unwrapped['id'])) {
        return unwrapped;
    }
    if (isArray(unwrapped)) {
        const match = unwrapped.find((entry: JsonValue | null | undefined) => isModelEntryMatch(entry, modelId));
        return match && isObject(match) ? match : null;
    }
    return null;
};

const isModelDetailStillPresent = (modelId: string | null, payload: JsonValue | null | undefined): boolean => {
    if (!modelId) {
        return false;
    }
    return extractModelDetailPayload(modelId, payload) !== null;
};

export { extractModelDetailPayload, isModelDetailStillPresent };
