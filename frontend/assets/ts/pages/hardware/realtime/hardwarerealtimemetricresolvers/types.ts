/* SoAI - Realtime hardware metric resolver contracts [frontend/assets/ts/pages/hardware/realtime/hardwarerealtimemetricresolvers/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { NetworkSpeedSnapshot } from '@features/hardware/public.ts';
import type { DeviceSelection, HardwarePageSnapshot } from '@pages/hardware/types.ts';

type ChartOhlcNumericContract = {
    resolveNumeric: (...values: (JsonValue | undefined)[]) => number | null;
};

type RealtimeMetricResolverContext = {
    metricKey: string | undefined;
    selectedTarget: DeviceSelection;
    payload: HardwarePageSnapshot;
    networkSpeedSources: (NetworkSpeedSnapshot | undefined)[];
    chartOhlc: ChartOhlcNumericContract;
};

export type { ChartOhlcNumericContract, DeviceSelection, RealtimeMetricResolverContext };
