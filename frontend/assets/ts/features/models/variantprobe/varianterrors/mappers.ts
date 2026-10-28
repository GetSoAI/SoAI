/* SoAI - Variant probe error mapping [frontend/assets/ts/features/models/variantprobe/varianterrors/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readApiErrorField } from '@core/apiError.ts';
import { extractUserFacingErrorMessage } from '@core/errors/coerce.ts';
import { resolveOperationCauseMessage } from '@core/errors/operationCausePresentation.ts';
import { isString } from '@core/typeGuards.ts';

const buildVariantProbeErrorMessage = (error: Error): string | null => {
    const code = readApiErrorField(error, 'code');
    return resolveOperationCauseMessage(isString(code) ? code : null, error) ?? extractUserFacingErrorMessage(error);
};

export { buildVariantProbeErrorMessage };
