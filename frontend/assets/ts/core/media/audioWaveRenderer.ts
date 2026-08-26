/* SoAI - Audio waveform oscilloscope renderer [frontend/assets/ts/core/media/audioWaveRenderer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { rgba, type CanvasRgb, type CanvasSize } from '@core/media/audioVisualizerCanvas.ts';

const LINE_WIDTH = 2;

const drawWaveActive = (context: CanvasRenderingContext2D, size: CanvasSize, color: CanvasRgb, buffer: Uint8Array<ArrayBuffer>): void => {
    context.lineCap = 'round';
    context.lineJoin = 'round';
    context.lineWidth = LINE_WIDTH;
    context.strokeStyle = rgba(color, 1);
    context.beginPath();
    const sliceWidth = size.width / buffer.length;
    let position = 0;
    for (let index = 0; index < buffer.length; index += 1) {
        const value = buffer[index] ?? 128;
        const yCoordinate = (value / 255) * size.height;
        if (index === 0) {
            context.moveTo(position, yCoordinate);
        } else {
            context.lineTo(position, yCoordinate);
        }
        position += sliceWidth;
    }
    context.stroke();
};

export { drawWaveActive };
