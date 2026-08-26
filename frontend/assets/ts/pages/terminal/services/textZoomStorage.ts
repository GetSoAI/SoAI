/* SoAI - Terminal page text zoom storage [frontend/assets/ts/pages/terminal/services/textZoomStorage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasFunctionProperty, isFunction, isNumber, isObject } from '@core/typeGuards.ts';
import type { TerminalTextZoomStorage } from '@pages/terminal/types.ts';

interface TerminalTextZoomStorageWithGetter extends TerminalTextZoomStorage {
    getTerminalTextZoom(fallback: number): number | null;
}

interface TerminalTextZoomStorageWithSetter extends TerminalTextZoomStorage {
    setTerminalTextZoom(value: number): void;
}

const isTerminalTextZoomStorage = <T>(value: T): value is T & TerminalTextZoomStorage => {
    if (!isObject(value)) {
        return false;
    }
    const getOk = !('getTerminalTextZoom' in value) || value.getTerminalTextZoom === undefined || hasFunctionProperty(value, 'getTerminalTextZoom');
    const setOk = !('setTerminalTextZoom' in value) || value.setTerminalTextZoom === undefined || hasFunctionProperty(value, 'setTerminalTextZoom');
    return getOk && setOk;
};

const hasTerminalTextZoomGetter = (value: TerminalTextZoomStorage): value is TerminalTextZoomStorageWithGetter => {
    return isFunction(value.getTerminalTextZoom);
};

const hasTerminalTextZoomSetter = (value: TerminalTextZoomStorage): value is TerminalTextZoomStorageWithSetter => {
    return isFunction(value.setTerminalTextZoom);
};

const tryGetTerminalTextZoom = <T>(storage: T, fallback: number): number | null => {
    if (!isTerminalTextZoomStorage(storage)) {
        return null;
    }
    if (!hasTerminalTextZoomGetter(storage)) {
        return null;
    }
    const value = storage.getTerminalTextZoom(fallback);
    return isNumber(value) ? value : null;
};

const trySetTerminalTextZoom = <T>(storage: T, value: number): void => {
    if (!isTerminalTextZoomStorage(storage)) {
        return;
    }
    if (!hasTerminalTextZoomSetter(storage)) {
        return;
    }
    storage.setTerminalTextZoom(value);
};

const getStoredTerminalFontSize = <T>(storage: T, baseFontSize: number): number => {
    const zoom = tryGetTerminalTextZoom(storage, 1) ?? 1;
    const normalizedZoom = zoom > 0 ? zoom : 1;
    return Math.round(baseFontSize * normalizedZoom);
};

const saveStoredTerminalFontSize = <T>(storage: T, baseFontSize: number, fontSize: number): void => {
    const zoom = fontSize / baseFontSize;
    if (!Number.isFinite(zoom) || zoom <= 0) {
        return;
    }
    trySetTerminalTextZoom(storage, zoom);
};

export { getStoredTerminalFontSize, saveStoredTerminalFontSize };
