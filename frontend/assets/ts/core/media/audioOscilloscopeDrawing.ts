/* SoAI - Audio visualizer mode dispatch [frontend/assets/ts/core/media/audioOscilloscopeDrawing.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getPerformance } from '@core/environment/public.ts';
import { drawAbstractActive } from '@core/media/audioAbstractRenderer.ts';
import { drawBarsActive } from '@core/media/audioBarsRenderer.ts';
import { prepareCanvas, prepareRetainedCanvas } from '@core/media/audioVisualizerCanvas.ts';
import { drawWaveActive } from '@core/media/audioWaveRenderer.ts';

type AudioOscilloscopeMode = 'wave' | 'bars' | 'abstract';

const currentTime = (): number => getPerformance().now();

const drawIdleOscilloscope = (canvas: HTMLCanvasElement): void => {
    prepareCanvas(canvas);
};

const drawActiveOscilloscope = (canvas: HTMLCanvasElement, analyser: AnalyserNode, buffer: Uint8Array<ArrayBuffer>, mode: AudioOscilloscopeMode): void => {
    if (mode === 'abstract') {
        const { context, size, color } = prepareRetainedCanvas(canvas);
        analyser.getByteTimeDomainData(buffer);
        drawAbstractActive(context, size, color, buffer, currentTime());
        return;
    }
    const { context, size, color } = prepareCanvas(canvas);
    if (mode === 'bars') {
        analyser.getByteFrequencyData(buffer);
        drawBarsActive(context, size, color, buffer, currentTime());
        return;
    }
    analyser.getByteTimeDomainData(buffer);
    drawWaveActive(context, size, color, buffer);
};

export { drawActiveOscilloscope, drawIdleOscilloscope };
export type { AudioOscilloscopeMode };
