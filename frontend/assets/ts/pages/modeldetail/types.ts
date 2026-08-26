/* SoAI - Model detail page public contracts [frontend/assets/ts/pages/modeldetail/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ParametersPayload } from '@pages/modeldetail/contracts/parameterTypes.ts';

export type ModelDetailParametersData = ParametersPayload & {
    type?: string | undefined;
    strategy?: string | undefined;
    models?: JsonValue[] | undefined;
};
