/* SoAI - Chat attach modal camera capture runtime [frontend/assets/ts/features/chat/composerattachmodal/cameraCapture.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { waitForTimerDelay } from '@core/concurrency/timerDelay.ts';
import { getWindow } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { createDeferred } from '@core/runtime/deferred.ts';

interface ChatAttachCameraElements {
    pane: HTMLElement;
    stage: HTMLElement;
    video: HTMLVideoElement;
    canvas: HTMLCanvasElement;
    status: HTMLElement;
    shutterButton: HTMLButtonElement;
    retakeButton: HTMLButtonElement;
    useButton: HTMLButtonElement;
    flipButton: HTMLButtonElement;
}

interface ChatAttachCameraRuntime {
    setAvailable(enabled: boolean): void;
    activate(): Promise<void>;
    deactivate(): void;
    capture(): Promise<void>;
    retake(): Promise<void>;
    useCapturedFile(): Promise<File | null>;
    flipCamera(): Promise<void>;
    dispose(): void;
}

type CameraFacingMode = 'environment' | 'user';

const PERMISSION_RETRY_DELAY_MS = 800;

const probeCameraPermissionState = async (): Promise<PermissionState | null> => {
    const permissions = navigator.permissions;
    if (!permissions || typeof permissions.query !== 'function') {
        return null;
    }
    try {
        const status = await permissions.query({ name: 'camera' });
        return status.state;
    } catch (error) {
        errorHandler.debug('ChatAttachCamera', 'Camera permission state is not queryable', ensureError(error));
        return null;
    }
};

const setButtonState = (button: HTMLButtonElement, enabled: boolean): void => {
    button.disabled = !enabled;
    button.setAttribute('aria-disabled', enabled ? 'false' : 'true');
};

const setButtonAvailability = (button: HTMLButtonElement, visible: boolean, enabled: boolean): void => {
    button.hidden = !visible;
    setButtonState(button, visible && enabled);
};

const stopStream = (stream: MediaStream | null): void => {
    if (stream === null) {
        return;
    }
    for (const track of stream.getTracks()) {
        track.stop();
    }
};

const renderStatus = (element: HTMLElement, text: string): void => {
    element.textContent = text;
    element.hidden = text.length === 0;
};

const setCameraState = (elements: ChatAttachCameraElements, state: string): void => {
    elements.pane.dataset['cameraState'] = state;
};

const syncStageAspectRatio = (elements: ChatAttachCameraElements, width: number, height: number): void => {
    elements.stage.style.setProperty('--chat-attach-camera-aspect-ratio', `${width} / ${height}`);
};

const createJpegBlob = (canvas: HTMLCanvasElement): Promise<Blob> => {
    const deferred = createDeferred<Blob>();
    if (typeof canvas.toBlob !== 'function') {
        deferred.reject(new Error('Camera capture canvas blob encoding is unavailable'));
        return deferred.promise;
    }
    canvas.toBlob(
        (blob) => {
            if (blob === null) {
                deferred.reject(new Error('Camera capture produced an empty image'));
                return;
            }
            deferred.resolve(blob);
        },
        'image/jpeg',
        0.92
    );
    return deferred.promise;
};

const requireVideoFrame = (video: HTMLVideoElement): { width: number; height: number } => {
    const width = video.videoWidth;
    const height = video.videoHeight;
    if (width <= 0 || height <= 0) {
        throw new Error('Camera video frame is unavailable');
    }
    return { width, height };
};

const resolveCameraStartFailureMessage = (error: Error): string => {
    if (error.name === 'NotFoundError' || error.name === 'DevicesNotFoundError') {
        return i18n.t('chat.attachModal.cameraNoCamera');
    }
    if (error.name === 'NotReadableError' || error.name === 'TrackStartError' || error.name === 'AbortError') {
        return i18n.t('chat.attachModal.cameraCaptureUnavailable');
    }
    if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
        return i18n.t('chat.attachModal.cameraPermissionDenied');
    }
    return i18n.t('chat.attachModal.cameraCaptureUnavailable');
};

const createCameraCaptureRuntime = (elements: ChatAttachCameraElements, signal: AbortSignal): ChatAttachCameraRuntime => {
    let enabled = false;
    let active = false;
    let stream: MediaStream | null = null;
    let capturedFile: File | null = null;
    let facingMode: CameraFacingMode = 'environment';
    let operationSequence = 0;
    let streamReady = false;

    const nextOperationSequence = (): number => {
        operationSequence += 1;
        return operationSequence;
    };

    const isCurrentOperation = (sequence: number): boolean => active && !signal.aborted && sequence === operationSequence;

    const syncControls = (): void => {
        const canUseCamera = active && enabled && streamReady;
        const hasCapture = capturedFile !== null;
        setButtonAvailability(elements.flipButton, !hasCapture, canUseCamera);
        setButtonAvailability(elements.shutterButton, !hasCapture, canUseCamera);
        setButtonAvailability(elements.retakeButton, hasCapture, active && enabled);
        setButtonAvailability(elements.useButton, hasCapture, active && enabled);
        if (!active) {
            setCameraState(elements, 'idle');
        } else if (!enabled) {
            setCameraState(elements, 'disabled');
        } else if (hasCapture) {
            setCameraState(elements, 'captured');
        }
    };

    const clearCapture = (): void => {
        capturedFile = null;
        elements.canvas.hidden = true;
        elements.video.hidden = false;
    };

    const stopActiveStream = (): void => {
        stopStream(stream);
        stream = null;
        streamReady = false;
        elements.video.srcObject = null;
    };

    const start = async (): Promise<void> => {
        const sequence = nextOperationSequence();
        stopActiveStream();
        clearCapture();
        if (!enabled) {
            renderStatus(elements.status, i18n.t('chat.attachModal.cameraDisabled'));
            setCameraState(elements, 'disabled');
            syncControls();
            return;
        }
        const mediaDevices = navigator.mediaDevices;
        if (!mediaDevices || typeof mediaDevices.getUserMedia !== 'function') {
            renderStatus(elements.status, i18n.t('chat.attachModal.cameraNoCamera'));
            setCameraState(elements, 'unsupported');
            syncControls();
            return;
        }
        setCameraState(elements, 'preparing');
        renderStatus(elements.status, i18n.t('chat.attachModal.cameraPreparing'));
        try {
            const constraints: MediaStreamConstraints = { audio: false, video: { facingMode } };
            let nextStream: MediaStream;
            try {
                nextStream = await mediaDevices.getUserMedia(constraints);
            } catch (firstError) {
                const coercedFirst = ensureError(firstError);
                const isPermissionError = coercedFirst.name === 'NotAllowedError' || coercedFirst.name === 'PermissionDeniedError';
                if (isPermissionError && isCurrentOperation(sequence)) {
                    const permissionState = await probeCameraPermissionState();
                    if (permissionState !== 'granted') {
                        throw coercedFirst;
                    }
                    await waitForTimerDelay(getWindow(), PERMISSION_RETRY_DELAY_MS, signal);
                    if (!isCurrentOperation(sequence)) {
                        return;
                    }
                    nextStream = await mediaDevices.getUserMedia(constraints);
                } else {
                    throw coercedFirst;
                }
            }
            if (!isCurrentOperation(sequence)) {
                stopStream(nextStream);
                return;
            }
            stream = nextStream;
            elements.video.srcObject = stream;
            await elements.video.play();
            const frame = requireVideoFrame(elements.video);
            syncStageAspectRatio(elements, frame.width, frame.height);
            if (!isCurrentOperation(sequence)) {
                stopActiveStream();
                return;
            }
            streamReady = true;
            setCameraState(elements, 'streaming');
            renderStatus(elements.status, '');
        } catch (error) {
            if (!isCurrentOperation(sequence)) {
                return;
            }
            const runtimeError = ensureError(error);
            errorHandler.warn('ChatAttachCamera', 'Camera stream request failed', runtimeError);
            setCameraState(elements, 'unavailable');
            renderStatus(elements.status, resolveCameraStartFailureMessage(runtimeError));
        }
        syncControls();
    };

    const runtime: ChatAttachCameraRuntime = {
        setAvailable(nextEnabled): void {
            enabled = nextEnabled;
            syncControls();
        },
        async activate(): Promise<void> {
            active = true;
            await start();
        },
        deactivate(): void {
            active = false;
            nextOperationSequence();
            stopActiveStream();
            clearCapture();
            syncControls();
        },
        async capture(): Promise<void> {
            if (!active || !enabled || !streamReady || capturedFile !== null) {
                return;
            }
            const sequence = nextOperationSequence();
            const frame = requireVideoFrame(elements.video);
            elements.canvas.width = frame.width;
            elements.canvas.height = frame.height;
            const context = elements.canvas.getContext('2d');
            if (context === null) {
                throw new Error(i18n.t('chat.attachModal.cameraCaptureUnavailable'));
            }
            context.drawImage(elements.video, 0, 0, frame.width, frame.height);
            const blob = await createJpegBlob(elements.canvas);
            if (!isCurrentOperation(sequence)) {
                return;
            }
            capturedFile = new File([blob], 'camera-capture.jpg', { type: 'image/jpeg' });
            stopActiveStream();
            elements.video.hidden = true;
            elements.canvas.hidden = false;
            syncStageAspectRatio(elements, frame.width, frame.height);
            setCameraState(elements, 'captured');
            syncControls();
        },
        async retake(): Promise<void> {
            if (!active) {
                return;
            }
            await start();
        },
        async useCapturedFile(): Promise<File | null> {
            if (!active || !enabled) {
                return null;
            }
            if (capturedFile === null && !streamReady) {
                return null;
            }
            if (capturedFile === null) {
                await runtime.capture();
            }
            return capturedFile;
        },
        async flipCamera(): Promise<void> {
            if (!active || capturedFile !== null) {
                return;
            }
            facingMode = facingMode === 'environment' ? 'user' : 'environment';
            await start();
        },
        dispose(): void {
            active = false;
            nextOperationSequence();
            stopActiveStream();
            clearCapture();
            syncControls();
        }
    };

    const disposeCameraRuntime = (): void => runtime.dispose();
    signal.addEventListener('abort', disposeCameraRuntime, { once: true });
    syncControls();
    return runtime;
};
export { createCameraCaptureRuntime };
export type { ChatAttachCameraElements, ChatAttachCameraRuntime };
