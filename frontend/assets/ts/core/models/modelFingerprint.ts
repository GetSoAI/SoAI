/* SoAI - Shared models model fingerprint [frontend/assets/ts/core/models/modelFingerprint.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { stableJsonStringify } from '@core/serialization/json.ts';
import { isNumber } from '@core/typeGuards.ts';
import { isJsonArray, isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';

const stableModelFingerprint = (candidate: JsonValue): string => {
    if (!isJsonObject(candidate)) return '';
    const capabilities = isJsonObject(candidate['openaiCapabilities']) ? candidate['openaiCapabilities'] : null;
    const providerMetadata = isJsonObject(candidate['providerMetadata']) ? candidate['providerMetadata'] : null;
    const modalities = isJsonArray(candidate['modalities']) ? candidate['modalities'].map((value) => String(value)) : [];
    const constituents = isNumber(candidate['constituents']) ? candidate['constituents'] : null;
    const virtualMembers = isJsonArray(candidate['models']) ? candidate['models'] : null;
    return stableJsonStringify({
        universalId: toTrimmedString(candidate['universalId']),
        id: toTrimmedString(candidate['id']),
        modelId: toTrimmedString(candidate['modelId']),
        sourceModelId: toTrimmedString(candidate['sourceModelId']),
        rawUpstreamModelId: toTrimmedString(candidate['rawUpstreamModelId']),
        name: toTrimmedString(candidate['name']),
        displayName: toTrimmedString(candidate['displayName']),
        alias: toTrimmedString(candidate['alias']),
        description: toTrimmedString(candidate['description']),
        type: toTrimmedString(candidate['type']),
        modelType: toTrimmedString(candidate['modelType']),
        plugin: toTrimmedString(candidate['plugin']),
        pluginName: toTrimmedString(candidate['pluginName']),
        provider: toTrimmedString(candidate['provider']),
        providerId: toTrimmedString(candidate['providerId']),
        providerName: toTrimmedString(candidate['providerName']),
        providerMetadataName: toTrimmedString(providerMetadata?.['name']),
        status: toTrimmedString(candidate['status']),
        pluginStatus: toTrimmedString(candidate['pluginStatus']),
        strategy: toTrimmedString(candidate['strategy']),
        isEnabled: candidate['isEnabled'] === true,
        isAvailable: candidate['isAvailable'] === true,
        available: candidate['available'] === true,
        isLoaded: candidate['isLoaded'] === true,
        loaded: candidate['loaded'] === true,
        isOrphaned: candidate['isOrphaned'] === true,
        hasAlias: candidate['hasAlias'] === true,
        modelHasCustomParameters: candidate['modelHasCustomParameters'] === true,
        sizeBytes: isNumber(candidate['sizeBytes']) ? candidate['sizeBytes'] : null,
        contextWindowTokens: isNumber(candidate['contextWindowTokens']) ? candidate['contextWindowTokens'] : null,
        openaiCapabilities: capabilities,
        modalities,
        constituents,
        models: virtualMembers
    });
};

export { stableModelFingerprint };
