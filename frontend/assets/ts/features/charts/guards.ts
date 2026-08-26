/* SoAI - Charts feature validation [frontend/assets/ts/features/charts/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFiniteNumber, isObject } from '@core/typeGuards.ts';
import type { PointerState } from '@features/charts/chartTypes.ts';
import type { PinchMetrics, PointerRecord } from '@features/charts/types.ts';

const getPinchMetrics = (p1: PointerRecord, p2: PointerRecord): PinchMetrics => ({
    dist: Math.max(10, Math.hypot(p2.clientX - p1.clientX, p2.clientY - p1.clientY)),
    cx: (p1.clientX + p2.clientX) / 2,
    cy: (p1.clientY + p2.clientY) / 2
});

const resolvePointerRecord = <T>(value: T): PointerRecord | null => {
    if (!isObject(value)) {
        return null;
    }
    if (!('clientX' in value) || !('clientY' in value)) {
        return null;
    }
    const clientX = value.clientX;
    const clientY = value.clientY;
    if (!isFiniteNumber(clientX) || !isFiniteNumber(clientY)) {
        return null;
    }
    const id = 'id' in value ? value.id : null;
    const type = 'type' in value ? value.type : null;
    const xCoordinate = 'x' in value ? value.x : null;
    const yCoordinate = 'y' in value ? value.y : null;
    const record: PointerRecord = { clientX, clientY };
    if (isFiniteNumber(id)) {
        record.id = id;
    }
    if (typeof type === 'string') {
        record.type = type;
    }
    if (isFiniteNumber(xCoordinate)) {
        record.x = xCoordinate;
    }
    if (isFiniteNumber(yCoordinate)) {
        record.y = yCoordinate;
    }
    return record;
};

const resolveFirstTwoPointers = (state: PointerState): [PointerRecord, PointerRecord] | null => {
    const values = Array.from(state.activePointers.values());
    if (values.length < 2) {
        return null;
    }
    const p1 = resolvePointerRecord(values[0]);
    const p2 = resolvePointerRecord(values[1]);
    if (!p1 || !p2) {
        return null;
    }
    return [p1, p2];
};

export { getPinchMetrics, resolveFirstTwoPointers, resolvePointerRecord };
