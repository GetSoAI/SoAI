/* SoAI - Model renaming modal mapping [frontend/assets/ts/features/models/modals/renamemodal/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';

const resolveCurrentModelAlias = (model: ModelRecord): string => {
    if (model.hasAlias !== true) {
        return '';
    }
    return toTrimmedString(model.alias) || toTrimmedString(model.displayName) || toTrimmedString(model.id) || toTrimmedString(model.name);
};

const resolveModelUniversalId = (model: ModelRecord): string => toTrimmedString(model.universalId);

const hasRenameFormChanges = (currentAlias: string, originalAlias: string): boolean => currentAlias !== originalAlias;

export { hasRenameFormChanges, resolveCurrentModelAlias, resolveModelUniversalId };
