/* SoAI - Shared license service contracts [frontend/assets/ts/core/licenseservice/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';

interface ClipboardCopyOptions {
    successMessage?: string | undefined;
    errorMessage?: string | undefined;
    notify?: ((message: string, type: string) => void) | undefined;
}

interface ClipboardServiceInterface {
    copyText(text: string, options?: ClipboardCopyOptions): Promise<boolean>;
}

interface InitializableLanguageService {
    initialize(): Promise<JsonValue> | JsonValue;
}

interface LicenseData {
    licenseText?: string;
}

interface CreateButtonOptions {
    text?: string;
    className?: string;
    id?: string | null;
}

type TextModalKey = 'license' | 'credits';

interface TextModalConfig {
    id: string;
    key: TextModalKey;
    className: string;
}

interface ModalButtonRefs {
    closeButton: HTMLButtonElement | null;
    copyButton: HTMLButtonElement | null;
}

interface LicenseServiceInterface {
    initialize(): Promise<void>;
    fetchLicenseData(): Promise<LicenseData>;
    showLicense(): Promise<void>;
    showCredits(): Promise<void>;
    handleCopy(key: TextModalKey): Promise<void>;
}

export type { ClipboardCopyOptions, ClipboardServiceInterface, CreateButtonOptions, InitializableLanguageService, LicenseData, LicenseServiceInterface, ModalButtonRefs, NotificationType, TextModalConfig, TextModalKey };
