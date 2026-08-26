/* SoAI - Model deletion eligibility policy [frontend/assets/ts/core/models/modelDeletionEligibility.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { isObject } from '@core/typeGuards.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';

const isProviderBackedModelRecord = (model: ModelRecord): boolean => {
    if (toTrimmedString(model.providerId)) return true;
    if (isObject(model.provider) || isObject(model.providerMetadata)) return true;
    return toTrimmedString(model.modelType).toLowerCase() === 'external';
};

const canDeleteModelRecord = (model: ModelRecord, plugin: PluginRecord | null): boolean => {
    if (model.type === 'virtual') return true;
    if (isProviderBackedModelRecord(model)) return false;
    return plugin?.capabilities?.supportsModelDeletion === true;
};

export { canDeleteModelRecord, isProviderBackedModelRecord };
