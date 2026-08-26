/* SoAI - Scale-aware canvas geometry [frontend/assets/ts/core/layout/canvasGeometry.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getDevicePixelRatio } from '@core/environment/public.ts';
import { interfaceScaleFactorFromScope } from '@core/layout/interfaceScale.ts';
import { isDocumentNode } from '@core/typeGuards.ts';

const resolveCanvasRenderPixelRatio = (scope: Document | Element): number => {
    const documentRef = isDocumentNode(scope) ? scope : scope.ownerDocument;
    const scopedDevicePixelRatio = documentRef.defaultView?.devicePixelRatio;
    const devicePixelRatio = typeof scopedDevicePixelRatio === 'number' && Number.isFinite(scopedDevicePixelRatio) && scopedDevicePixelRatio > 0 ? scopedDevicePixelRatio : getDevicePixelRatio();
    return devicePixelRatio * interfaceScaleFactorFromScope(scope);
};

export { resolveCanvasRenderPixelRatio };
