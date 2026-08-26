/* SoAI - Metrics page support [frontend/assets/ts/pages/metrics/contracts/MetricsPageSupport.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createModuleLogger } from '@core/runtime/runtimeContext.ts';

const PAGE_ID = 'metrics';
const PAGE_MODULE_ID = 'pages.MetricsPage';
const metricsLogger = createModuleLogger('MetricsPage', { defaultLevel: 'warn' });

export { PAGE_ID, PAGE_MODULE_ID, metricsLogger };
