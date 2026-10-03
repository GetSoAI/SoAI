/* SoAI - Settings immediate background selection [frontend/assets/ts/pages/settings/controllers/thememanager/backgroundSelection.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DefaultWallpaperId } from '@core/theme/defaultWallpapers.ts';
import type { ThemeManagerHost } from '@pages/settings/controllers/thememanager/contracts.ts';

type BackgroundSelectionHost = Pick<ThemeManagerHost, 'storage' | 'scheduleWallpaperRefresh'>;

const commitSolidBackground = (host: BackgroundSelectionHost, color: string | null): void => {
    host.storage.setSolidBackground(color);
    if (color !== null) {
        host.storage.setDefaultWallpaper(null);
    }
    host.scheduleWallpaperRefresh();
};

const commitDefaultWallpaper = (host: BackgroundSelectionHost, id: DefaultWallpaperId | null): void => {
    host.storage.setDefaultWallpaper(id);
    if (id !== null) {
        host.storage.setSolidBackground(null);
    }
    host.scheduleWallpaperRefresh();
};

export { commitDefaultWallpaper, commitSolidBackground };
