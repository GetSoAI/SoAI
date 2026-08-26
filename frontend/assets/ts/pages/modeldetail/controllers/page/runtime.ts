/* SoAI - Model detail page control layer runtime [frontend/assets/ts/pages/modeldetail/controllers/page/runtime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { isString } from '@core/typeGuards.ts';
import type { ModelDetailSession } from '@pages/modeldetail/state/ModelDetailSession.ts';

const resetModelDetailPageBeforeInitialize = (session: ModelDetailSession, capabilityState: { reset(): void }, parameters: Record<string, JsonValue>): void => {
    const idCandidate = parameters['id'];
    session.resetForInitialization(isString(idCandidate) && idCandidate.trim() ? idCandidate : null);
    capabilityState.reset();
};

export { resetModelDetailPageBeforeInitialize };
