/* SoAI - Shared page context clipboard service [frontend/assets/ts/core/pagecontext/clipboard/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ClipboardApi, ClipboardCopyInput, ClipboardCopyOptions, ClipboardNotificationHandler, ClipboardService } from '@core/pagecontext/contracts.ts';
import { isObject } from '@core/typeGuards.ts';

type ClipboardServiceCandidate = Partial<ClipboardService>;

const isClipboardServiceCandidate = <T>(value: T): value is T & ClipboardServiceCandidate => isObject(value);
const isClipboardCopyTextFunction = <T>(value: T): value is T & ClipboardService['copyText'] => typeof value === 'function';
const isClipboardIsSupportedFunction = <T>(value: T): value is T & NonNullable<ClipboardService['isSupported']> => typeof value === 'function';
const isClipboardNotificationRegistrationFunction = <T>(value: T): value is T & NonNullable<ClipboardService['registerNotificationHandler']> => typeof value === 'function';
const isDisposerFunction = <T>(value: T): value is T & (() => void) => typeof value === 'function';

const isClipboardService = <T>(value: T): value is T & ClipboardService => isClipboardServiceCandidate(value) && isClipboardCopyTextFunction(value.copyText);

const createClipboardApi = <T>(service: T): ClipboardApi => {
    if (!service) {
        throw new Error('PageContext requires a clipboard service');
    }
    if (!isClipboardService(service)) throw new Error('Clipboard service must expose copyText');
    const clipboardService = service;
    const isSupported = (): boolean => {
        if (!isClipboardIsSupportedFunction(clipboardService.isSupported)) {
            return false;
        }
        return clipboardService.isSupported?.() === true;
    };
    const registerNotificationHandler = (handler: ClipboardNotificationHandler): (() => void) => {
        if (!isClipboardNotificationRegistrationFunction(clipboardService.registerNotificationHandler)) {
            return () => {};
        }
        const disposerCandidate = clipboardService.registerNotificationHandler?.(handler);
        if (!isDisposerFunction(disposerCandidate)) {
            throw new Error('Clipboard registerNotificationHandler must return a disposer function');
        }
        return () => {
            void disposerCandidate();
        };
    };
    return Object.freeze({
        isSupported,
        copyText: async (text: ClipboardCopyInput, options?: ClipboardCopyOptions) => clipboardService.copyText(text, options),
        registerNotificationHandler
    });
};

export { createClipboardApi };
