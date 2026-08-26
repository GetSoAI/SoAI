/* SoAI - Variant probe error mapping [frontend/assets/ts/pages/models/controllers/variantprobemanager/varianterrors/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { extractUserFacingErrorMessage } from '@core/errors/coerce.ts';

const buildVariantProbeErrorMessage = (error: Error): string | null => {
    return extractUserFacingErrorMessage(error);
};

export { buildVariantProbeErrorMessage };
