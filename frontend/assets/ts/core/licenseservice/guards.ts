/* SoAI - Shared license service validation [frontend/assets/ts/core/licenseservice/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ClipboardService } from '@core/clipboard.ts';
import type { LanguageService } from '@core/languageservice/service.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ClipboardServiceInterface, InitializableLanguageService, LicenseServiceInterface } from '@core/licenseservice/types.ts';

type LicenseServiceGuardCandidate = ClipboardService | ClipboardServiceInterface | InitializableLanguageService | JsonValue | LanguageService | LicenseServiceInterface | null;

const isInitializableLanguageService = (value: LicenseServiceGuardCandidate): value is InitializableLanguageService => isObject(value) && 'initialize' in value && isFunction(value.initialize);

const isClipboardService = (value: LicenseServiceGuardCandidate): value is ClipboardServiceInterface => isObject(value) && 'copyText' in value && isFunction(value.copyText);

const isLicenseService = (value: LicenseServiceGuardCandidate): value is LicenseServiceInterface => isObject(value) && 'fetchLicenseData' in value && isFunction(value.fetchLicenseData) && 'showLicense' in value && isFunction(value.showLicense) && 'showCredits' in value && isFunction(value.showCredits);

export { isClipboardService, isInitializableLanguageService, isLicenseService };
