/* SoAI - Settings page control layer theme manager mapping [frontend/assets/ts/pages/settings/controllers/thememanager/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { formatKilobytesFromBytes } from '@core/primitives/byteSize.ts';
import type { WallpaperMetadata } from '@core/settings/contracts.ts';

const formatWallpaperInfo = (metadata: WallpaperMetadata | null): string => {
    if (!metadata) {
        return '';
    }

    const parts: string[] = [];
    if (metadata.width && metadata.height) {
        parts.push(`${metadata.width}x${metadata.height}`);
    }
    if (metadata.type) {
        parts.push(metadata.type);
    }
    if (metadata.sizeBytes) {
        parts.push(formatKilobytesFromBytes(metadata.sizeBytes));
    }
    return parts.join(' · ');
};

const formatWallpaperOverlayValue = (percent: number): string => i18n.t('settings.wallpaper.overlay.value', { percent });

export { formatWallpaperInfo, formatWallpaperOverlayValue };
