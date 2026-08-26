/* SoAI - Shared page context telemetry service [frontend/assets/ts/core/pagecontext/telemetry/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TelemetryService } from '@core/pagecontext/contracts.ts';
import { isObject } from '@core/typeGuards.ts';

type TelemetryServiceCandidate = Partial<TelemetryService>;

const isTelemetryServiceCandidate = <T>(value: T): value is T & TelemetryServiceCandidate => isObject(value);

const isTelemetryEmit = <T>(value: T): value is T & TelemetryService['emit'] => typeof value === 'function';

const isTelemetryGetMetric = <T>(value: T): value is T & NonNullable<TelemetryService['getMetric']> => typeof value === 'function';

const isTelemetryObserveMetric = <T>(value: T): value is T & NonNullable<TelemetryService['observeMetric']> => typeof value === 'function';

const isTelemetrySubscribe = <T>(value: T): value is T & NonNullable<TelemetryService['subscribe']> => typeof value === 'function';

const isTelemetryGetStatus = <T>(value: T): value is T & NonNullable<TelemetryService['getStatus']> => typeof value === 'function';

const ensureTelemetry = <T>(telemetry: T): TelemetryService => {
    if (!telemetry) {
        throw new Error('PageContext requires a telemetry service');
    }
    if (!isTelemetryServiceCandidate(telemetry)) throw new Error('Telemetry service must expose emit');
    const emitValue = telemetry.emit;
    if (!isTelemetryEmit(emitValue)) throw new Error('Telemetry service must expose emit');
    const result: TelemetryService = { emit: emitValue };
    const getMetricValue = telemetry.getMetric;
    if (isTelemetryGetMetric(getMetricValue)) {
        result.getMetric = getMetricValue;
    }
    const observeMetricValue = telemetry.observeMetric;
    if (isTelemetryObserveMetric(observeMetricValue)) {
        result.observeMetric = observeMetricValue;
    }
    const subscribeValue = telemetry.subscribe;
    if (isTelemetrySubscribe(subscribeValue)) {
        result.subscribe = subscribeValue;
    }
    const getStatusValue = telemetry.getStatus;
    if (isTelemetryGetStatus(getStatusValue)) {
        result.getStatus = getStatusValue;
    }
    return result;
};

export { ensureTelemetry };
