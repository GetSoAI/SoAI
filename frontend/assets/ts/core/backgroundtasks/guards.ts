/* SoAI - Shared background tasks validation [frontend/assets/ts/core/backgroundtasks/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isBoolean, isFunction, isObject } from '@core/typeGuards.ts';
import type { AuthInstance, StorageInstance } from '@core/backgroundtasks/types.ts';

const isStorageInstance = <T>(value: T): value is T & StorageInstance => isObject(value) && 'getSolidBackground' in value && isFunction(value.getSolidBackground) && 'getWallpaperOverlay' in value && isFunction(value.getWallpaperOverlay);

const isAuthInstance = <T>(value: T): value is T & AuthInstance => isObject(value) && 'isAuthenticated' in value && isBoolean(value.isAuthenticated);

export { isAuthInstance, isStorageInstance };
