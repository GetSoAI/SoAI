/* SoAI - Crisp device-pixel QR matrix rendering onto a canvas [frontend/assets/ts/core/qr/qrCanvasRenderer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireNonNull } from '@core/assertions.ts';
import { getComputedStyleStrict } from '@core/environment/public.ts';
import { resolveCanvasRenderPixelRatio } from '@core/layout/canvasGeometry.ts';
import { measureElementLayoutDimensions } from '@core/layout/elementGeometry.ts';
import type { QrMatrix } from '@core/qr/qrEncoder.ts';

interface QrCanvasRect {
    readonly x: number;
    readonly y: number;
    readonly width: number;
    readonly height: number;
}

interface QrCanvasPlan {
    readonly pixelSize: number;
    readonly modulePixels: number;
    readonly darkRects: readonly QrCanvasRect[];
}

interface QrCanvasPalette {
    readonly dark: string;
    readonly light: string;
}

const QR_QUIET_ZONE_MODULES = 4;

const planQrCanvas = (matrix: QrMatrix, cssSize: number, pixelRatio: number): QrCanvasPlan | null => {
    const pixelSize = Math.floor(cssSize * pixelRatio);
    const totalModules = matrix.size + QR_QUIET_ZONE_MODULES * 2;
    const modulePixels = Math.floor(pixelSize / totalModules);
    if (!Number.isFinite(modulePixels) || modulePixels < 1) return null;
    const origin = Math.floor((pixelSize - modulePixels * totalModules) / 2) + QR_QUIET_ZONE_MODULES * modulePixels;
    const darkRects: QrCanvasRect[] = [];
    for (let row = 0; row < matrix.size; row += 1) {
        let runStart = -1;
        for (let column = 0; column <= matrix.size; column += 1) {
            const dark = column < matrix.size && requireNonNull(matrix.modules[row * matrix.size + column], 'QR matrix module') === 1;
            if (dark && runStart < 0) runStart = column;
            if (dark || runStart < 0) continue;
            darkRects.push({ x: origin + runStart * modulePixels, y: origin + row * modulePixels, width: (column - runStart) * modulePixels, height: modulePixels });
            runStart = -1;
        }
    }
    return { pixelSize, modulePixels, darkRects };
};

const resolveQrCanvasPalette = (canvas: HTMLCanvasElement): QrCanvasPalette => {
    const style = getComputedStyleStrict(canvas);
    return { dark: style.color, light: style.backgroundColor };
};

const drawQrCanvas = (canvas: HTMLCanvasElement, plan: QrCanvasPlan, palette: QrCanvasPalette): void => {
    const context = canvas.getContext('2d');
    if (!context) throw new Error('QR rendering requires a 2D canvas context');
    if (canvas.width !== plan.pixelSize || canvas.height !== plan.pixelSize) {
        canvas.width = plan.pixelSize;
        canvas.height = plan.pixelSize;
    }
    context.setTransform(1, 0, 0, 1, 0, 0);
    context.imageSmoothingEnabled = false;
    context.fillStyle = palette.light;
    context.fillRect(0, 0, plan.pixelSize, plan.pixelSize);
    context.fillStyle = palette.dark;
    for (const rect of plan.darkRects) context.fillRect(rect.x, rect.y, rect.width, rect.height);
};

const renderQrCanvas = (canvas: HTMLCanvasElement, matrix: QrMatrix): boolean => {
    const plan = planQrCanvas(matrix, measureElementLayoutDimensions(canvas).width, resolveCanvasRenderPixelRatio(canvas));
    if (plan === null) return false;
    drawQrCanvas(canvas, plan, resolveQrCanvasPalette(canvas));
    return true;
};

export { planQrCanvas, renderQrCanvas };
export type { QrCanvasPlan, QrCanvasRect };
