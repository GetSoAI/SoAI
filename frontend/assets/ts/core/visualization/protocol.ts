/* SoAI - Offscreen visualization messages [frontend/assets/ts/core/visualization/protocol.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isObject, isString, isPositiveInteger, isArray, isFiniteNumber } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

interface SpinnerGradientStop {
    position: number;
    color: string;
}

interface SpinnerTrailAppearance {
    width: number;
    height: number;
    trailWidth: number;
    trailHeight: number;
    duration: number;
    stops: SpinnerGradientStop[];
}

type VisualizationRequest = { type: 'initializeSpinner'; canvas: OffscreenCanvas; appearance: SpinnerTrailAppearance } | { type: 'renderSpinner'; appearance: SpinnerTrailAppearance } | { type: 'suspend' };
type VisualizationResponse = { type: 'ready' } | { type: 'unavailable'; reason: string };

const isSpinnerGradientStop = (value: SpinnerGradientStop | null | undefined): value is SpinnerGradientStop => isObject(value) && isString(value.color) && value.color.length > 0 && isFiniteNumber(value.position) && value.position >= 0 && value.position <= 1;

const isSpinnerTrailAppearance = (value: SpinnerTrailAppearance | JsonValue | null | undefined): value is SpinnerTrailAppearance => {
    if (!isObject(value)) return false;
    const appearance: Partial<SpinnerTrailAppearance> = value;
    if (!isPositiveInteger(appearance.width) || !isPositiveInteger(appearance.height) || !isPositiveInteger(appearance.trailWidth) || !isPositiveInteger(appearance.trailHeight) || !isFiniteNumber(appearance.duration) || appearance.duration <= 0) return false;
    if (!isArray(appearance.stops) || appearance.stops.length < 2 || appearance.stops.length > 32 || !appearance.stops.every(isSpinnerGradientStop)) return false;
    let previousPosition = -1;
    for (const stop of appearance.stops) {
        if (stop.position < previousPosition) return false;
        previousPosition = stop.position;
    }
    return appearance.stops[0]?.position === 0 && appearance.stops.at(-1)?.position === 1;
};

interface VisualizationRequestCandidate {
    type?: string | undefined;
    canvas?: OffscreenCanvas | undefined;
    appearance?: SpinnerTrailAppearance | undefined;
}

const isVisualizationRequest = (value: VisualizationRequest | JsonValue | null | undefined): value is VisualizationRequest => {
    if (!isObject(value)) return false;
    const request: VisualizationRequestCandidate = value;
    if (request.type === 'suspend') return true;
    if (request.type === 'renderSpinner') return isSpinnerTrailAppearance(request.appearance);
    if (typeof OffscreenCanvas !== 'function' || !(request.canvas instanceof OffscreenCanvas)) return false;
    return request.type === 'initializeSpinner' && isSpinnerTrailAppearance(request.appearance);
};

const decodeVisualizationResponse = (value: JsonValue | null | undefined): VisualizationResponse => {
    if (isObject(value)) {
        if (value['type'] === 'ready') return { type: 'ready' };
        if (value['type'] === 'unavailable' && isString(value['reason']) && value['reason']) return { type: 'unavailable', reason: value['reason'] };
    }
    throw new Error('Visualization worker returned an invalid response');
};

export { isSpinnerTrailAppearance, isVisualizationRequest, decodeVisualizationResponse };
export type { SpinnerGradientStop, SpinnerTrailAppearance, VisualizationRequest, VisualizationResponse };
