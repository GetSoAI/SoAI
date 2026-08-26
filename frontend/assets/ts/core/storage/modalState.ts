/* SoAI - Shared storage modal state [frontend/assets/ts/core/storage/modalState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModalState } from '@core/storage/types.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isFiniteNumber, isObject } from '@core/typeGuards.ts';

const normalizeSize = (value: JsonValue | undefined): JsonObject | null => {
    if (!isObject(value) || isArray(value)) {
        return null;
    }
    const width = value['width'];
    const height = value['height'];
    if (!isFiniteNumber(width) || !isFiniteNumber(height)) {
        return null;
    }
    return { width, height };
};

const normalizeModalState = (value: JsonValue | undefined): ModalState | null => {
    if (!isObject(value) || isArray(value)) {
        return null;
    }

    const size = normalizeSize(value['size']);
    if (size === null) {
        return null;
    }

    const state: ModalState = {};
    state['size'] = size;
    return state;
};

const normalizeModalStatesRecord = (value: JsonValue | undefined): Record<string, ModalState> | null => {
    if (!isObject(value) || isArray(value)) {
        return null;
    }

    const modalStates: Record<string, ModalState> = {};
    for (const [modalId, modalValue] of Object.entries(value)) {
        if (!modalId) {
            continue;
        }
        const state = normalizeModalState(modalValue);
        if (state) {
            modalStates[modalId] = state;
        }
    }
    return modalStates;
};

export { normalizeModalState, normalizeModalStatesRecord };
