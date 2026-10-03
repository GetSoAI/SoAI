/* SoAI - Shared page outlet constants [frontend/assets/ts/core/pageoutlet/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { PAGE_READINESS_TIMEOUT_MS } from '@core/constants.ts';

const READY_TIMEOUT_MS = PAGE_READINESS_TIMEOUT_MS;

const PAGE_OUTLET_RENDER_STAGES = Object.freeze({
    PREPARED: 'prepared',
    ACTIVATED: 'activated'
});

const PAGE_OUTLET_TIMEOUT_ERROR_NAME = 'PageOutletTimeoutError';

export { PAGE_OUTLET_RENDER_STAGES, PAGE_OUTLET_TIMEOUT_ERROR_NAME, READY_TIMEOUT_MS };
