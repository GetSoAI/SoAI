/* SoAI - Shared state contracts [frontend/assets/ts/core/state/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TelemetryValue } from '@core/telemetry/contracts.ts';

export interface DomService {
    resolve(selector: string, context?: Element | Document | null): Element | null;
    resolveAll(selector: string, context?: Element | Document | null): Element[];
    getDocument(): Document;
    getDocumentElement(): Element;
    toggleClass(element: Element, className: string, force?: boolean): void;
    addClass(element: Element, classes: string | string[]): void;
    removeClass(element: Element, classes: string | string[]): void;
    setText(element: Element, text: string): void;
    setHTML(element: Element, html: string, options?: { escape?: boolean }): void;
    setStyle(element: Element, property: string, value: string): void;
    getData(element: Element, key: string): string | null;
}

export interface ErrorHandler {
    debug?(module: string, message: string, error?: TelemetryValue): void;
    info?(module: string, message: string, error?: TelemetryValue): void;
    warn?(module: string, message: string, error?: TelemetryValue): void;
    error?(module: string, message: string, error?: TelemetryValue): void;
}
