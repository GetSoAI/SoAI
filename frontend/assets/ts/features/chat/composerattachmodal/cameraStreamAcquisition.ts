/* SoAI - Chat attach modal camera stream acquisition across available cameras [frontend/assets/ts/features/chat/composerattachmodal/cameraStreamAcquisition.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { waitForTimerDelay } from '@core/concurrency/timerDelay.ts';
import { getWindow } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { classifyMediaCaptureError } from '@core/media/mediaCaptureErrors.ts';
import { stopMediaStreamTracks } from '@core/media/mediaCleanup.ts';
import { isFunction } from '@core/typeGuards.ts';

interface CameraStreamRequest {
    mediaDevices: MediaDevices;
    deviceId: string | null;
    signal: AbortSignal;
    isCurrent: () => boolean;
}

interface OpenedCameraStream {
    stream: MediaStream;
    deviceId: string | null;
}

const PERMISSION_RETRY_DELAY_MS = 800;

const probeCameraPermissionState = async (): Promise<PermissionState | null> => {
    const permissions = navigator.permissions;
    if (!permissions || !isFunction(permissions.query)) {
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

const listCameraDeviceIds = async (mediaDevices: MediaDevices): Promise<readonly string[]> => {
    if (!isFunction(mediaDevices.enumerateDevices)) {
        return [];
    }
    try {
        const devices = await mediaDevices.enumerateDevices();
        return devices.filter((device) => device.kind === 'videoinput' && device.deviceId !== '').map((device) => device.deviceId);
    } catch (error) {
        errorHandler.warn('ChatAttachCamera', 'Camera devices are not enumerable', ensureError(error));
        return [];
    }
};

const selectNextCameraDeviceId = (deviceIds: readonly string[], currentDeviceId: string | null): string | null => {
    if (deviceIds.length === 0) {
        return null;
    }
    const currentIndex = currentDeviceId === null ? -1 : deviceIds.indexOf(currentDeviceId);
    return deviceIds[(currentIndex + 1) % deviceIds.length] ?? null;
};

const resolveCameraConstraints = (deviceId: string | null): MediaTrackConstraints => (deviceId === null ? { facingMode: 'environment' } : { deviceId: { exact: deviceId } });

const resolveStreamDeviceId = (stream: MediaStream, requestedDeviceId: string | null): string | null => {
    const videoTrack = stream.getVideoTracks()[0];
    if (videoTrack === undefined) {
        throw new Error('Camera stream does not contain a video track');
    }
    const settingsDeviceId = videoTrack.getSettings().deviceId;
    return settingsDeviceId === undefined || settingsDeviceId === '' ? requestedDeviceId : settingsDeviceId;
};

const requestCameraStream = async (request: CameraStreamRequest): Promise<MediaStream> => {
    const constraints: MediaStreamConstraints = { audio: false, video: resolveCameraConstraints(request.deviceId) };
    let firstError: Error;
    try {
        return await request.mediaDevices.getUserMedia(constraints);
    } catch (error) {
        firstError = ensureError(error);
    }
    if (classifyMediaCaptureError(firstError) !== 'permission' || !request.isCurrent() || (await probeCameraPermissionState()) !== 'granted') {
        throw firstError;
    }
    await waitForTimerDelay(getWindow(), PERMISSION_RETRY_DELAY_MS, request.signal);
    if (!request.isCurrent()) {
        throw firstError;
    }
    return request.mediaDevices.getUserMedia(constraints);
};

const openCameraStream = async (request: CameraStreamRequest): Promise<OpenedCameraStream> => {
    const stream = await requestCameraStream(request);
    try {
        return { stream, deviceId: resolveStreamDeviceId(stream, request.deviceId) };
    } catch (error) {
        stopMediaStreamTracks(stream);
        throw ensureError(error);
    }
};

export { listCameraDeviceIds, openCameraStream, selectNextCameraDeviceId };
