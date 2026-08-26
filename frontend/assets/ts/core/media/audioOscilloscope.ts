/* SoAI - Shared audio oscilloscope renderer [frontend/assets/ts/core/media/audioOscilloscope.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { resolveAudioContextConstructor } from '@core/media/audioCaptureSupport.ts';
import { drawActiveOscilloscope, drawIdleOscilloscope, type AudioOscilloscopeMode } from '@core/media/audioOscilloscopeDrawing.ts';
import { closeAudioContextSafe } from '@core/media/mediaCleanup.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';

type AudioOscilloscopeState = 'idle' | 'active' | 'unavailable';

type AudioOscilloscopeInstance = Readonly<{
    start: () => void;
    cycleMode: () => AudioOscilloscopeMode;
    dispose: () => void;
}>;

type AudioOscilloscopeArguments = Readonly<{
    media: HTMLMediaElement;
    canvas: HTMLCanvasElement;
    onStateChange: (state: AudioOscilloscopeState) => void;
}>;

const FFT_SIZE = 2048;
const VISUALIZATION_MODES: readonly AudioOscilloscopeMode[] = Object.freeze(['wave', 'bars', 'abstract']);

const createAudioOscilloscope = ({ media, canvas, onStateChange }: AudioOscilloscopeArguments): AudioOscilloscopeInstance => {
    const resources = new ResourceTracker();
    let disposed = false;
    let token = 0;
    let audioContext: AudioContext | null = null;
    let source: MediaElementAudioSourceNode | null = null;
    let analyser: AnalyserNode | null = null;
    let buffer: Uint8Array<ArrayBuffer> | null = null;
    let frameId: number | null = null;
    let visualizationAvailable = true;
    let modeIndex = 0;

    const stopFrame = (): void => {
        if (frameId !== null) {
            resources.cancelAnimationFrame(frameId);
            frameId = null;
        }
    };

    const markUnavailable = (): void => {
        visualizationAvailable = false;
        stopFrame();
        onStateChange('unavailable');
    };

    const disconnectAudioNode = (node: AudioNode | null, contextLabel: string): void => {
        if (!node) {
            return;
        }
        try {
            node.disconnect();
        } catch (error) {
            errorHandler.warn('AudioOscilloscope', `Failed to disconnect audio node (${contextLabel})`, ensureError(error));
        }
    };

    const closeAudioGraph = (contextLabel: string): void => {
        disconnectAudioNode(source, contextLabel);
        disconnectAudioNode(analyser, contextLabel);
        source = null;
        analyser = null;
        buffer = null;
        const context = audioContext;
        audioContext = null;
        terminateHandledPromise(closeAudioContextSafe(context, contextLabel));
    };

    const drawIdle = (): void => {
        stopFrame();
        if (disposed || !visualizationAvailable) {
            return;
        }
        onStateChange('idle');
        try {
            drawIdleOscilloscope(canvas);
        } catch (error) {
            const resolvedError = ensureError(error);
            errorHandler.warn('AudioOscilloscope', 'Failed to draw idle audio visualization', resolvedError);
            markUnavailable();
        }
    };

    const renderFrame = (): void => {
        if (disposed || !visualizationAvailable || media.paused || media.ended || !analyser || !buffer) {
            drawIdle();
            return;
        }
        onStateChange('active');
        try {
            drawActiveOscilloscope(canvas, analyser, buffer, VISUALIZATION_MODES[modeIndex] ?? 'wave');
        } catch (error) {
            const resolvedError = ensureError(error);
            errorHandler.warn('AudioOscilloscope', 'Failed to draw active audio visualization', resolvedError);
            markUnavailable();
            return;
        }
        frameId = resources.requestAnimationFrame(renderFrame);
    };

    const beginFrameLoop = (): void => {
        stopFrame();
        if (disposed || !visualizationAvailable) {
            return;
        }
        frameId = resources.requestAnimationFrame(renderFrame);
    };

    const initialize = async (initializationToken: number): Promise<void> => {
        if (disposed || !visualizationAvailable || initializationToken !== token) {
            return;
        }
        if (analyser && buffer) {
            beginFrameLoop();
            return;
        }
        const AudioContextConstructor = resolveAudioContextConstructor();
        const nextAudioContext = new AudioContextConstructor();
        audioContext = nextAudioContext;
        if (nextAudioContext.state === 'suspended') {
            await nextAudioContext.resume();
        }
        if (disposed || !visualizationAvailable || initializationToken !== token) {
            if (audioContext === nextAudioContext) {
                audioContext = null;
            }
            terminateHandledPromise(closeAudioContextSafe(nextAudioContext, 'audio oscilloscope abandoned setup'));
            return;
        }
        const nextSource = nextAudioContext.createMediaElementSource(media);
        const nextAnalyser = nextAudioContext.createAnalyser();
        source = nextSource;
        analyser = nextAnalyser;
        nextAnalyser.fftSize = FFT_SIZE;
        nextSource.connect(nextAnalyser);
        nextAnalyser.connect(nextAudioContext.destination);
        buffer = new Uint8Array(nextAnalyser.fftSize);
        beginFrameLoop();
    };

    const start = (): void => {
        if (disposed || !visualizationAvailable) {
            return;
        }
        token += 1;
        const initializationToken = token;
        void initialize(initializationToken).catch((error) => {
            if (!disposed && initializationToken === token) {
                const resolvedError = ensureError(error);
                closeAudioGraph('audio oscilloscope failed setup');
                errorHandler.warn('AudioOscilloscope', 'Audio visualization setup failed', resolvedError);
                markUnavailable();
            }
        });
    };

    const onInactive = (): void => {
        if (!disposed) {
            drawIdle();
        }
    };

    const cycleMode = (): AudioOscilloscopeMode => {
        if (disposed || !visualizationAvailable) {
            return VISUALIZATION_MODES[modeIndex] ?? 'wave';
        }
        modeIndex = (modeIndex + 1) % VISUALIZATION_MODES.length;
        if (media.paused || media.ended || !analyser || !buffer) {
            drawIdle();
        }
        return VISUALIZATION_MODES[modeIndex] ?? 'wave';
    };

    resources.addEventListener(media, 'play', start);
    resources.addEventListener(media, 'playing', start);
    resources.addEventListener(media, 'pause', onInactive);
    resources.addEventListener(media, 'ended', onInactive);
    resources.addEventListener(media, 'error', onInactive);

    try {
        if (typeof ResizeObserver !== 'function') {
            throw new Error('Audio oscilloscope requires ResizeObserver');
        }
        const resizeObserver = new ResizeObserver(() => {
            if (disposed || !visualizationAvailable) {
                return;
            }
            if (media.paused || media.ended) {
                drawIdle();
            }
        });
        resizeObserver.observe(canvas);
        resources.track(resizeObserver, (observer: ResizeObserver) => observer.disconnect());
        drawIdle();
    } catch (error) {
        const resolvedError = ensureError(error);
        errorHandler.warn('AudioOscilloscope', 'Audio visualization initialization failed', resolvedError);
        markUnavailable();
    }

    const dispose = (): void => {
        if (disposed) {
            return;
        }
        disposed = true;
        token += 1;
        stopFrame();
        resources.cleanup();
        closeAudioGraph('audio oscilloscope dispose');
    };

    return Object.freeze({ start, cycleMode, dispose });
};

export { createAudioOscilloscope };
export type { AudioOscilloscopeInstance, AudioOscilloscopeState };
