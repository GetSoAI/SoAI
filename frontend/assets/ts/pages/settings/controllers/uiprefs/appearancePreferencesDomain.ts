/* SoAI - Settings appearance preference ownership [frontend/assets/ts/pages/settings/controllers/uiprefs/appearancePreferencesDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { UiPreferences } from '@core/storage/types.ts';

const selectAppearanceUiPreferences = (preferences: Pick<UiPreferences, 'accentColor' | 'surfaceColor' | 'reduceMotions' | 'glassEnabled' | 'pageAnimation' | 'modalAnimation' | 'notificationAnimation' | 'animationSpeed' | 'wallpaperOverlay'>) => ({
    accentColor: preferences.accentColor,
    surfaceColor: preferences.surfaceColor,
    reduceMotions: preferences.reduceMotions,
    glassEnabled: preferences.glassEnabled,
    pageAnimation: preferences.pageAnimation,
    modalAnimation: preferences.modalAnimation,
    notificationAnimation: preferences.notificationAnimation,
    animationSpeed: preferences.animationSpeed,
    wallpaperOverlay: preferences.wallpaperOverlay
});

export { selectAppearanceUiPreferences };
