/* SoAI - Charts feature logger [frontend/assets/ts/features/charts/component/logger.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TelemetryValue } from '@core/telemetry/contracts.ts';
import { createChartLogger } from '@features/charts/logging.ts';

const logger = createChartLogger('ChartComponent', { defaultLevel: 'info' });

const logDebug = (message: string, detail?: TelemetryValue): void => logger.debug(message, detail);
const logInfo = (message: string, detail?: TelemetryValue): void => logger.info(message, detail);
const logWarn = (message: string, detail?: TelemetryValue): void => logger.warn(message, detail);
const logError = (message: string, detail?: TelemetryValue): void => logger.error(message, detail);

export { logger, logDebug, logError, logInfo, logWarn };
