/* SoAI - Shared language service validation [frontend/assets/ts/core/languageservice/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray, isFunction, isObject } from '@core/typeGuards.ts';
import type { ApiClient, TranslationObject, TranslationValue } from '@core/languageservice/types.ts';

const isTranslationObject = (value: TranslationValue): value is TranslationObject => isObject(value) && !isArray(value);

const isApiClient = <T>(value: T): value is T & ApiClient => isObject(value) && 'fetchAsset' in value && isFunction(value.fetchAsset);

export { isApiClient, isTranslationObject };
