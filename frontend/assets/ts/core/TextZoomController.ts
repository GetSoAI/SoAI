/* SoAI - Shared frontend text zoom controller [frontend/assets/ts/core/TextZoomController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getLogValidation, TEXT_ZOOM_MAX, TEXT_ZOOM_MIN } from '@core/logvalidation/public.ts';
import { CHAT_TEXT_ZOOM_DEFAULT, CHAT_TEXT_ZOOM_MAX, CHAT_TEXT_ZOOM_MIN } from '@core/chat/parameters/textZoom.ts';
import type { TextZoomResult } from '@core/logvalidation/types.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isFunction } from '@core/typeGuards.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

type LogLevel = 'debug' | 'info' | 'warn' | 'error';
type LoggerFunction = (level: LogLevel, message: string, error?: Error) => void;
type ZoomToCssMapper = (zoom: number) => string;
type ZoomGetter = (fallback: number) => number;
type ZoomSetter = (value: number) => void;

interface TextZoomOptions {
    cssVariable: string;
    defaultZoom?: number | undefined;
    minZoom?: number | undefined;
    maxZoom?: number | undefined;
    mapZoomToCss: ZoomToCssMapper;
    getStoredZoom: ZoomGetter;
    setStoredZoom: ZoomSetter;
    logger?: LoggerFunction | undefined;
    strictStorageContract?: boolean | undefined;
}

interface PageInterface extends PageDomOwnerHost {
    dom: {
        getDocumentElement: () => HTMLElement;
    };
}

interface ChatStorage {
    getChatTextZoom: (fallback: number) => number;
    setChatTextZoom: (value: number) => void;
}

interface LogsStorage {
    getLogsTextZoom: (fallback: number) => number;
    setLogsTextZoom: (value: number) => void;
}

class TextZoomController {
    private cssVariable: string;
    private defaultZoom: number;
    private minZoom: number;
    private maxZoom: number;
    private mapZoomToCss: ZoomToCssMapper;
    private getStoredZoom: ZoomGetter;
    private setStoredZoom: ZoomSetter;
    private logger: LoggerFunction | undefined;
    private strictStorageContract: boolean;
    currentZoom: number;

    constructor(options: TextZoomOptions) {
        if (!options || typeof options !== 'object') {
            throw new TypeError('TextZoomController options must be a non-null object');
        }
        const { cssVariable, defaultZoom = 1, minZoom = TEXT_ZOOM_MIN, maxZoom = TEXT_ZOOM_MAX, mapZoomToCss, getStoredZoom, setStoredZoom, logger, strictStorageContract = false } = options;
        if (!cssVariable || typeof cssVariable !== 'string') {
            throw new TypeError('TextZoomController requires a non-empty cssVariable');
        }
        if (!Number.isFinite(minZoom) || !Number.isFinite(maxZoom) || minZoom > maxZoom) {
            throw new TypeError('TextZoomController requires a valid zoom range');
        }
        if (!Number.isFinite(defaultZoom) || defaultZoom < minZoom || defaultZoom > maxZoom) {
            throw new TypeError('TextZoomController defaultZoom must be inside the zoom range');
        }
        if (!isFunction(mapZoomToCss)) {
            throw new TypeError('TextZoomController requires a mapZoomToCss function');
        }
        if (!isFunction(getStoredZoom)) {
            throw new TypeError('TextZoomController requires a getStoredZoom function');
        }
        if (!isFunction(setStoredZoom)) {
            throw new TypeError('TextZoomController requires a setStoredZoom function');
        }
        this.cssVariable = cssVariable;
        this.defaultZoom = defaultZoom;
        this.minZoom = minZoom;
        this.maxZoom = maxZoom;
        this.mapZoomToCss = mapZoomToCss;
        this.getStoredZoom = getStoredZoom;
        this.setStoredZoom = setStoredZoom;
        this.logger = logger;
        this.strictStorageContract = Boolean(strictStorageContract);
        this.currentZoom = defaultZoom;
    }

    initialize(page: PageInterface): number {
        this.assertStorageContract();
        const stored = this.getStoredZoom(this.defaultZoom);
        const validated = this.validateZoom(stored, 'Invalid stored text zoom') ?? this.defaultZoom;
        this.currentZoom = validated;
        if (validated !== stored) {
            this.persistZoom(validated);
        }
        this.applyZoom(page);
        return this.currentZoom;
    }

    scheduleInitialize(page: PageInterface, readyPromise: Promise<JsonValue | null | undefined>): void {
        if (!readyPromise || !isFunction(readyPromise.then)) {
            return;
        }
        readyPromise
            .then(() => {
                this.initialize(page);
            })
            .catch((error) => {
                this.log('warn', 'Failed to refresh text zoom after storage readiness', error);
            });
    }

    adjust(page: PageInterface, delta: number): number {
        if (!Number.isFinite(delta)) {
            throw new Error(`Invalid text zoom delta: ${delta}`);
        }
        const next = this.normalizeZoom(this.currentZoom + delta);
        const clamped = this.clampZoom(next);
        if (this.areNearlyEqual(clamped, this.currentZoom)) {
            this.currentZoom = clamped;
            this.applyZoom(page);
            return this.currentZoom;
        }
        const validated = this.validateZoom(clamped, 'Invalid text zoom adjustment');
        if (validated === null) {
            return this.currentZoom;
        }
        this.currentZoom = validated;
        this.persistZoom(validated);
        this.applyZoom(page);
        return this.currentZoom;
    }

    applyZoom(page: PageInterface): number {
        const validated = this.validateZoom(this.currentZoom, 'Invalid text zoom');
        this.currentZoom = validated ?? this.defaultZoom;
        const root = page.dom.getDocumentElement();
        const cssValue = this.mapZoomToCss(this.currentZoom);
        page.pageDom.updateStyle(root, this.cssVariable, cssValue);
        return this.currentZoom;
    }

    validateZoom(zoom: number, contextMessage: string): number | null {
        const result: TextZoomResult = getLogValidation().validateTextZoom(zoom);
        if (result.valid && typeof result.zoom === 'number') {
            return result.zoom;
        }
        const errorText = result.error;
        const detail = typeof errorText === 'string' && errorText.trim() ? errorText.trim() : '';
        const message = detail ? `${contextMessage}: ${detail}` : contextMessage;
        this.log('error', message);
        return null;
    }

    persistZoom(zoom: number): void {
        this.assertStorageContract();
        this.setStoredZoom(zoom);
        if (this.strictStorageContract && this.getStoredZoom(zoom) !== zoom) {
            this.log('error', 'Failed to persist text zoom to storage');
            throw new Error('Text zoom persistence failed');
        }
    }

    private normalizeZoom(value: number): number {
        if (!Number.isFinite(value)) {
            return value;
        }
        return Math.round(value * 10000) / 10000;
    }

    private clampZoom(value: number): number {
        if (!Number.isFinite(value)) {
            return value;
        }
        if (value < this.minZoom) {
            return this.minZoom;
        }
        if (value > this.maxZoom) {
            return this.maxZoom;
        }
        return value;
    }

    private areNearlyEqual(firstValue: number, secondValue: number): boolean {
        if (!Number.isFinite(firstValue) || !Number.isFinite(secondValue)) {
            return false;
        }
        return Math.abs(firstValue - secondValue) <= 0.0001;
    }

    assertStorageContract(): void {
        if (!this.strictStorageContract) {
            return;
        }
        if (!isFunction(this.getStoredZoom) || !isFunction(this.setStoredZoom)) {
            throw new Error('Storage service must expose text zoom accessors');
        }
    }

    log(level: LogLevel, message: string, error?: Error): void {
        if (!this.logger || !isFunction(this.logger)) {
            return;
        }
        this.logger(level, message, error);
    }

    static createForChat(storage: ChatStorage, logger?: LoggerFunction): TextZoomController {
        if (!storage) {
            throw new Error('Chat text zoom requires a storage service');
        }
        return new TextZoomController({
            cssVariable: '--chat-text-scale',
            defaultZoom: CHAT_TEXT_ZOOM_DEFAULT,
            minZoom: CHAT_TEXT_ZOOM_MIN,
            maxZoom: CHAT_TEXT_ZOOM_MAX,
            mapZoomToCss: (zoom: number) => String(zoom),
            getStoredZoom: (fallback: number) => storage.getChatTextZoom(fallback),
            setStoredZoom: (value: number) => storage.setChatTextZoom(value),
            logger,
            strictStorageContract: true
        });
    }

    static createForLogs(storage: LogsStorage, logger?: LoggerFunction): TextZoomController {
        if (!storage || !isFunction(storage.getLogsTextZoom) || !isFunction(storage.setLogsTextZoom)) {
            throw new Error('Logs text zoom requires storage with get/set methods');
        }
        return new TextZoomController({
            cssVariable: '--logs-font-size',
            defaultZoom: 1,
            mapZoomToCss: (zoom: number) => `${zoom * 0.75}rem`,
            getStoredZoom: (fallback: number) => storage.getLogsTextZoom(fallback),
            setStoredZoom: (value: number) => storage.setLogsTextZoom(value),
            logger,
            strictStorageContract: true
        });
    }
}

export { TextZoomController };
