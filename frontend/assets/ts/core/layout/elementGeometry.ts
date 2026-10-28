/* SoAI - Centralized viewport and layout geometry measurement [frontend/assets/ts/core/layout/elementGeometry.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isDocument } from '@core/dom/domEnvironment.ts';
import { getComputedStyleStrict, getDocumentElement } from '@core/environment/public.ts';
import { interfaceScaleFactorFromRoot } from '@core/layout/interfaceScale.ts';

interface GeometryBox {
    x: number;
    y: number;
    left: number;
    top: number;
    right: number;
    bottom: number;
    width: number;
    height: number;
}

interface GeometryPoint {
    x: number;
    y: number;
}

interface GeometryDimensions {
    width: number;
    height: number;
}

type GeometryMeasurable = Element | Range;
type PointerGeometryEvent = MouseEvent | PointerEvent;
const resolveMeasurementDocument = (measurable: GeometryMeasurable): Document => {
    const ancestor = 'commonAncestorContainer' in measurable ? measurable.commonAncestorContainer : measurable;
    const documentRef = isDocument(ancestor) ? ancestor : ancestor.ownerDocument;
    if (!documentRef) {
        throw new Error('Geometry measurement requires an owning document');
    }
    return documentRef;
};

const resolveScopeDocument = (scope: Document | Element): Document => (isDocument(scope) ? scope : scope.ownerDocument);

const toLayoutPixels = (viewportPixels: number, scope: Document | Element = getDocumentElement()): number => {
    const root = resolveScopeDocument(scope).documentElement;
    return viewportPixels / interfaceScaleFactorFromRoot(root);
};

const measureLayoutViewport = (scope: Document | Element = getDocumentElement()): GeometryDimensions => {
    const documentRef = resolveScopeDocument(scope);
    const view = documentRef.defaultView;
    if (!view) {
        throw new Error('Layout viewport measurement requires an owning window');
    }
    const scale = interfaceScaleFactorFromRoot(documentRef.documentElement);
    return {
        width: view.innerWidth / scale,
        height: view.innerHeight / scale
    };
};

const measureElementLayoutDimensions = (element: HTMLElement): GeometryDimensions => ({
    width: element.clientWidth,
    height: element.clientHeight
});

const createGeometryBox = (rectangle: DOMRect | DOMRectReadOnly, divisor: number): GeometryBox => ({
    x: rectangle.x / divisor,
    y: rectangle.y / divisor,
    left: rectangle.left / divisor,
    top: rectangle.top / divisor,
    right: rectangle.right / divisor,
    bottom: rectangle.bottom / divisor,
    width: rectangle.width / divisor,
    height: rectangle.height / divisor
});

const SCROLLBAR_PROBE_CLASS = 'ui-scrollbar-probe';

const measureScrollbarInlineSize = (scope: Document | Element = getDocumentElement()): number => {
    const documentRef = resolveScopeDocument(scope);
    const probe = documentRef.createElement('div');
    probe.className = SCROLLBAR_PROBE_CLASS;
    documentRef.body.append(probe);
    const inlineSize = Math.max(0, probe.offsetWidth - probe.clientWidth);
    probe.remove();
    return inlineSize;
};

const measureViewportBox = (measurable: GeometryMeasurable): GeometryBox => createGeometryBox(measurable.getBoundingClientRect(), 1);

const measureLayoutBox = (measurable: GeometryMeasurable): GeometryBox => {
    const root = resolveMeasurementDocument(measurable).documentElement;
    return createGeometryBox(measurable.getBoundingClientRect(), interfaceScaleFactorFromRoot(root));
};

const GRID_LINE_NAMES_PATTERN = /\[[^\]]*\]/g;
const RESOLVED_GRID_TRACK_PATTERN = /^\d+(?:\.\d+)?px$/;

const measureGridColumnCount = (element: Element): number | null => {
    if (!element.isConnected) return null;
    const tracks = getComputedStyleStrict(element).gridTemplateColumns.replace(GRID_LINE_NAMES_PATTERN, ' ').trim().split(/\s+/);
    return tracks.length > 0 && tracks.every((track) => RESOLVED_GRID_TRACK_PATTERN.test(track)) ? tracks.length : null;
};

const measureViewportPoint = (event: PointerGeometryEvent): GeometryPoint => ({ x: event.clientX, y: event.clientY });

const measureLayoutPoint = (event: PointerGeometryEvent, scope: Document | Element = getDocumentElement()): GeometryPoint => ({
    x: toLayoutPixels(event.clientX, scope),
    y: toLayoutPixels(event.clientY, scope)
});

const measureViewportTouchPoint = (touch: Touch): GeometryPoint => ({ x: touch.clientX, y: touch.clientY });

const measureLayoutTouchPoint = (touch: Touch, scope: Document | Element = getDocumentElement()): GeometryPoint => ({
    x: toLayoutPixels(touch.clientX, scope),
    y: toLayoutPixels(touch.clientY, scope)
});

export { measureElementLayoutDimensions, measureGridColumnCount, measureLayoutBox, measureLayoutPoint, measureLayoutTouchPoint, measureLayoutViewport, measureScrollbarInlineSize, measureViewportBox, measureViewportPoint, measureViewportTouchPoint, toLayoutPixels };
export type { GeometryBox, GeometryDimensions, GeometryMeasurable, GeometryPoint, PointerGeometryEvent };
