/* SoAI - Shared attachment upload pipeline for chat file/camera inputs [frontend/assets/ts/features/chat/attachments/attachmentUploadPipeline.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { fetchSystemLimits, getCameraVisionImageOptimizationEnabled, getCameraVisionUploadEnabled } from '@core/api/systemLimitsService.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import type { ModuleLogger } from '@core/moduleContext.ts';
import { isSupportedChatImageFile } from '@features/chat/ChatAttachmentSupport.ts';
import { createChatUploadFileTooLargeMessage, getChatUploadFileSizeLimit } from '@features/chat/attachments/attachmentValidation.ts';
import { normalizeImageMimeTypeFromHeader } from '@features/chat/imageMimeSniffer.ts';
import { optimizeCameraImageFileForVision } from '@features/chat/CameraVisionImageOptimizer.ts';

type ErrorHandler = (error: Error, title: string, options?: { notify?: boolean }) => void;

type AttachmentUploadSource = 'picker' | 'camera' | 'folder';

type HandleChatAttachmentUploadArguments = {
    files: File[];
    source: AttachmentUploadSource;
    visionSupported: boolean;
    handleFiles: (files: File[], options?: { forceDocument?: boolean }) => Promise<void>;
    logger: ModuleLogger;
    errorHandler: ErrorHandler;
};

const notifyLimitsUnavailable = (inputArguments: HandleChatAttachmentUploadArguments): void => {
    const title = i18n.t('chat.upload.errorTitle');
    const message = inputArguments.source === 'camera' ? i18n.t('chat.upload.cameraLimitsUnavailable') : i18n.t('chat.upload.limitsUnavailable');
    inputArguments.errorHandler(new Error(message), title, { notify: true });
};

const resolveCameraOptimizationErrorMessage = (error: Error, fileName: string): string | null => {
    const message = error.message;
    if (message === 'CHAT_CAMERA_IMAGE_TOO_LARGE') {
        return i18n.t('chat.upload.cameraImageTooLarge', { name: fileName });
    }
    if (message === 'CHAT_CAMERA_IMAGE_OBJECT_URL_UNAVAILABLE' || message === 'CHAT_CAMERA_IMAGE_ENCODE_UNSUPPORTED') {
        return i18n.t('chat.upload.cameraBrowserUnsupported');
    }
    if (message === 'CHAT_CAMERA_IMAGE_DECODE_FAILED') {
        return i18n.t('chat.upload.cameraUnsupportedImage', { name: fileName });
    }
    if (message === 'CHAT_CAMERA_IMAGE_RENDER_FAILED' || message === 'CHAT_CAMERA_IMAGE_ENCODE_FAILED' || message === 'CHAT_CAMERA_IMAGE_INVALID_DIMENSIONS') {
        return i18n.t('chat.upload.cameraUnsupportedImage', { name: fileName });
    }
    if (message === 'CHAT_IMAGE_UNSUPPORTED_TYPE') {
        return i18n.t('chat.upload.cameraUnsupportedImage', { name: fileName });
    }
    return null;
};

const handleCameraUploads = async (inputArguments: HandleChatAttachmentUploadArguments): Promise<void> => {
    const errorTitle = i18n.t('chat.upload.errorTitle');

    if (!inputArguments.visionSupported || !getCameraVisionUploadEnabled()) {
        await inputArguments.handleFiles(inputArguments.files, { forceDocument: true });
        return;
    }

    const optimizationEnabled = getCameraVisionImageOptimizationEnabled();
    const sizeLimit = getChatUploadFileSizeLimit();

    const optimizedFiles: File[] = [];
    for (const file of inputArguments.files) {
        if (file.size > sizeLimit.maxBytes) {
            inputArguments.errorHandler(new Error(createChatUploadFileTooLargeMessage(file.name, sizeLimit)), errorTitle, { notify: true });
            continue;
        }

        let normalizedFile: File | null;
        try {
            normalizedFile = await normalizeImageMimeTypeFromHeader(file);
        } catch (error) {
            const runtimeError = ensureError(error);
            inputArguments.logger('warn', 'Camera image MIME normalization failed', {
                fileName: file.name,
                message: runtimeError.message,
                name: runtimeError.name,
                stack: runtimeError.stack ?? null
            });
            inputArguments.errorHandler(new Error(i18n.t('chat.upload.cameraUnsupportedImage', { name: file.name })), errorTitle, { notify: true });
            continue;
        }
        if (normalizedFile === null) {
            inputArguments.errorHandler(new Error(i18n.t('chat.upload.cameraUnsupportedImage', { name: file.name })), errorTitle, { notify: true });
            continue;
        }

        if (!optimizationEnabled) {
            optimizedFiles.push(normalizedFile);
            continue;
        }

        try {
            const optimized = await optimizeCameraImageFileForVision(normalizedFile, { maxPixels: 4_000_000, jpegQuality: 0.85, maxOutputBytes: sizeLimit.maxBytes });
            if (optimized.size > sizeLimit.maxBytes) {
                inputArguments.errorHandler(new Error(createChatUploadFileTooLargeMessage(file.name, sizeLimit)), errorTitle, { notify: true });
                continue;
            }
            optimizedFiles.push(optimized);
        } catch (error) {
            const runtimeError = ensureError(error);
            const message = resolveCameraOptimizationErrorMessage(runtimeError, file.name) ?? i18n.t('chat.upload.cameraOptimizationFailed', { name: file.name });
            inputArguments.logger('warn', 'Camera image optimization failed', {
                fileName: file.name,
                optimizationError: runtimeError.message,
                optimizationReason: message,
                name: runtimeError.name,
                stack: runtimeError.stack ?? null
            });
            inputArguments.errorHandler(new Error(message), errorTitle, { notify: true });
        }
    }

    if (optimizedFiles.length === 0) {
        return;
    }
    await inputArguments.handleFiles(optimizedFiles);
};

const handlePickerUploads = async (inputArguments: HandleChatAttachmentUploadArguments): Promise<void> => {
    const errorTitle = i18n.t('chat.upload.errorTitle');
    const sizeLimit = getChatUploadFileSizeLimit();

    const cameraVisionUploadEnabled = getCameraVisionUploadEnabled();
    if (!inputArguments.visionSupported || !cameraVisionUploadEnabled) {
        await inputArguments.handleFiles(inputArguments.files, { forceDocument: true });
        return;
    }

    const optimizationEnabled = getCameraVisionImageOptimizationEnabled();
    const visionImageCandidates: File[] = [];
    const forceDocumentCandidates: File[] = [];
    for (const file of inputArguments.files) {
        if (isSupportedChatImageFile(file)) {
            visionImageCandidates.push(file);
            continue;
        }
        forceDocumentCandidates.push(file);
    }

    const optimizedVisionFiles: File[] = [];
    for (const file of visionImageCandidates) {
        if (file.size > sizeLimit.maxBytes) {
            inputArguments.errorHandler(new Error(createChatUploadFileTooLargeMessage(file.name, sizeLimit)), errorTitle, { notify: true });
            continue;
        }
        let normalizedFile: File | null;
        try {
            normalizedFile = await normalizeImageMimeTypeFromHeader(file);
        } catch (error) {
            const runtimeError = ensureError(error);
            inputArguments.logger('warn', 'Picker image MIME normalization failed; using document attachment flow', {
                fileName: file.name,
                message: runtimeError.message,
                name: runtimeError.name,
                stack: runtimeError.stack ?? null
            });
            forceDocumentCandidates.push(file);
            continue;
        }
        if (normalizedFile === null) {
            forceDocumentCandidates.push(file);
            continue;
        }
        if (!optimizationEnabled) {
            optimizedVisionFiles.push(normalizedFile);
            continue;
        }
        try {
            const optimized = await optimizeCameraImageFileForVision(normalizedFile, { maxPixels: 4_000_000, jpegQuality: 0.85, maxOutputBytes: sizeLimit.maxBytes });
            if (optimized.size > sizeLimit.maxBytes) {
                inputArguments.errorHandler(new Error(createChatUploadFileTooLargeMessage(file.name, sizeLimit)), errorTitle, { notify: true });
                continue;
            }
            optimizedVisionFiles.push(optimized);
        } catch (error) {
            const runtimeError = ensureError(error);
            const message = resolveCameraOptimizationErrorMessage(runtimeError, file.name) ?? i18n.t('chat.upload.cameraOptimizationFailed', { name: file.name });
            inputArguments.logger('warn', 'Vision image optimization failed', {
                fileName: file.name,
                message,
                optimizationError: runtimeError.message,
                name: runtimeError.name,
                stack: runtimeError.stack ?? null
            });
            inputArguments.errorHandler(new Error(message), errorTitle, { notify: true });
        }
    }

    if (optimizedVisionFiles.length > 0) {
        await inputArguments.handleFiles(optimizedVisionFiles);
    }
    if (forceDocumentCandidates.length > 0) {
        await inputArguments.handleFiles(forceDocumentCandidates, { forceDocument: true });
    }
};

const handleChatAttachmentUploadPipeline = async (inputArguments: HandleChatAttachmentUploadArguments): Promise<void> => {
    if (inputArguments.files.length === 0) {
        return;
    }

    try {
        await fetchSystemLimits();
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.error('ChatAttachmentUploadPipeline', 'Failed to fetch system limits for attachment upload', runtimeError);
        notifyLimitsUnavailable(inputArguments);
        return;
    }

    if (inputArguments.source === 'camera') {
        await handleCameraUploads(inputArguments);
        return;
    }
    await handlePickerUploads(inputArguments);
};

export { handleChatAttachmentUploadPipeline };
export type { AttachmentUploadSource, HandleChatAttachmentUploadArguments };
