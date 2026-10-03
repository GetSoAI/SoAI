/* SoAI - Charts feature contracts [frontend/assets/ts/features/charts/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';

interface WheelPayload {
    clientX: number;
    clientY: number;
    deltaX: number;
    deltaY: number;
    deltaMode: number;
    shiftKey: boolean;
    ctrlKey: boolean;
    metaKey: boolean;
}

interface PointerEventInput {
    clientX: number;
    clientY: number;
    button?: number | undefined;
    pointerType?: string | undefined;
    preventDefault?: (() => void) | undefined;
}

interface PinchMetrics {
    dist: number;
    cx: number;
    cy: number;
}

interface PointerRecord {
    id?: number;
    type?: string;
    clientX: number;
    clientY: number;
    x?: number;
    y?: number;
    [key: string]: JsonValue | null | undefined;
}

interface CrosshairUpdatePayload {
    x: number;
    dataIndex: number;
    rawIndex: number;
    value: number | null;
    timestamp: number | null;
    open: number | null;
    high: number | null;
    low: number | null;
    close: number | null;
    datasetValues?: Record<string, number>;
    [key: string]: JsonValue | null | undefined;
}

export type { CrosshairUpdatePayload, PinchMetrics, PointerEventInput, PointerRecord, WheelPayload };
