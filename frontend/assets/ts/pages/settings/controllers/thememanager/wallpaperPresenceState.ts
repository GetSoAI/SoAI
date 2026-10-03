/* SoAI - Settings page wallpaper presence view model [frontend/assets/ts/pages/settings/controllers/thememanager/wallpaperPresenceState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';

type WallpaperPresence = 'unknown' | 'absent' | 'present';

interface WallpaperUploadControlView {
    label: string;
    help: string;
    buttonText: string;
    removes: boolean;
}

interface WallpaperView {
    previewVisible: boolean;
    messageVisible: boolean;
    overlayApplicable: boolean;
    detailsApplicable: boolean;
    builtInApplicable: boolean;
    solidApplicable: boolean;
    upload: WallpaperUploadControlView;
}

const WALLPAPER_UPLOAD_VARIANT_CLASS = 'ui-variant-neutral';
const WALLPAPER_REMOVE_VARIANT_CLASS = 'ui-variant-danger';

const resolveWallpaperView = (presence: WallpaperPresence, builtInSelected: boolean): WallpaperView => {
    const present = presence === 'present';
    const absent = presence === 'absent';
    const wallpaperVisible = present || (absent && builtInSelected);
    return {
        previewVisible: wallpaperVisible,
        messageVisible: absent && !builtInSelected,
        overlayApplicable: wallpaperVisible,
        detailsApplicable: present,
        builtInApplicable: absent,
        solidApplicable: absent,
        upload: present
            ? {
                  label: i18n.t('settings.wallpaper.remove.label'),
                  help: i18n.t('settings.wallpaper.remove.help'),
                  buttonText: i18n.t('settings.wallpaper.remove.button'),
                  removes: true
              }
            : {
                  label: i18n.t('settings.wallpaper.upload.label'),
                  help: i18n.t('settings.wallpaper.upload.help'),
                  buttonText: i18n.t('settings.wallpaper.upload.button'),
                  removes: false
              }
    };
};

const resolveWallpaperUploadVariantClass = (upload: WallpaperUploadControlView): string => (upload.removes ? WALLPAPER_REMOVE_VARIANT_CLASS : WALLPAPER_UPLOAD_VARIANT_CLASS);

export { resolveWallpaperUploadVariantClass, resolveWallpaperView, WALLPAPER_REMOVE_VARIANT_CLASS, WALLPAPER_UPLOAD_VARIANT_CLASS };
export type { WallpaperPresence, WallpaperUploadControlView, WallpaperView };
