/* SoAI - Chart OHLC rendering constants [frontend/assets/ts/features/charts/ohlc/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TelemetryValue } from '@core/telemetry/contracts.ts';
import { createChartLogger } from '@features/charts/logging.ts';

const OHLC = 'ohlc';

const chartOhlcLogger = createChartLogger('ChartOhlc', { defaultLevel: 'warn' });

const logWarn = (message: string, detail?: TelemetryValue): void => {
    chartOhlcLogger.warn(message, detail);
};

const logDebug = (message: string, detail?: TelemetryValue): void => {
    chartOhlcLogger.debug(message, detail);
};

const logError = (message: string, detail?: TelemetryValue): void => {
    chartOhlcLogger.error(message, detail);
};

export { OHLC, logDebug, logError, logWarn };
