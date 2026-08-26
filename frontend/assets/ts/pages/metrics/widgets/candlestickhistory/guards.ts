/* SoAI - Metrics page candlestick history validation [frontend/assets/ts/pages/metrics/widgets/candlestickhistory/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasFunctionProperty, isObject } from '@core/typeGuards.ts';
import type { OhlcParserHost } from '@pages/metrics/widgets/candlestickhistory/types.ts';

const isOhlcParserHost = <T>(value: T): value is T & OhlcParserHost => {
    return isObject(value) && hasFunctionProperty(value, 'parseBackendOhlcResponse');
};

export { isOhlcParserHost };
