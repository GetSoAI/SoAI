/* SoAI - Built-in wallpaper catalog [frontend/assets/ts/core/theme/defaultWallpapers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveAssetPath } from '@core/assetPaths.ts';
import { isNumber } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

type DefaultWallpaperId = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10;

const DEFAULT_WALLPAPER_IDS: readonly DefaultWallpaperId[] = Object.freeze([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);

const isDefaultWallpaperId = (value: JsonValue | null | undefined): value is DefaultWallpaperId => isNumber(value) && DEFAULT_WALLPAPER_IDS.some((id) => id === value);

const resolveDefaultWallpaperUrl = (id: DefaultWallpaperId): string => resolveAssetPath(`img/wallpaper/${id}.webp`);

const resolveDefaultWallpaperThumbnailUrl = (id: DefaultWallpaperId): string => resolveAssetPath(`img/wallpaper/thumb/${id}.webp`);

export { DEFAULT_WALLPAPER_IDS, isDefaultWallpaperId, resolveDefaultWallpaperThumbnailUrl, resolveDefaultWallpaperUrl };
export type { DefaultWallpaperId };
