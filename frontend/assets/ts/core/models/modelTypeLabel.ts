/* SoAI - Localized model type label resolution [frontend/assets/ts/core/models/modelTypeLabel.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString } from '@core/normalize.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';

const resolveModelTypeLabel = (model: ModelRecord | null): string | null => {
    const type = model ? toTrimmedString(model.type) : '';
    if (type === 'local') {
        return i18n.t('models.types.local');
    }
    if (type === 'cloud') {
        return i18n.t('models.types.cloud');
    }
    if (type === 'virtual') {
        return i18n.t('models.types.virtual');
    }
    return null;
};

export { resolveModelTypeLabel };
