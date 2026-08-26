/* SoAI - Settings page theme manager rendering [frontend/assets/ts/pages/settings/controllers/thememanager/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderSection } from '@core/settings/settingsMarkup.ts';
import { renderSecondaryThemeSubgroups } from '@pages/settings/controllers/thememanager/adapters.ts';
import { renderAppearanceSubgroup, renderCodeBlocksSubgroup } from '@pages/settings/controllers/thememanager/appearanceWidget.ts';
import { renderEffectsSubgroup } from '@pages/settings/controllers/thememanager/effectsWidget.ts';
import type { ThemeViewContext } from '@pages/settings/controllers/thememanager/contracts.ts';
import { renderSolidBackgroundSubgroup, renderWallpaperSubgroup } from '@pages/settings/controllers/thememanager/wallpaperWidget.ts';

const renderThemeSection = (context: ThemeViewContext): string => {
    const subgroups = [renderAppearanceSubgroup(context), renderCodeBlocksSubgroup(context), renderEffectsSubgroup(context)];
    if (context.canManageWallpaper) {
        subgroups.push(renderWallpaperSubgroup(context));
    } else if (context.canManageSolidBackground) {
        subgroups.push(renderSolidBackgroundSubgroup(context));
    }
    subgroups.push(...renderSecondaryThemeSubgroups(context));

    return renderSection({
        title: i18n.t('settings.theme.sectionTitle'),
        description: i18n.t('settings.theme.description'),
        className: 'settings-section--theme',
        content: subgroups.join('')
    });
};

export { renderThemeSection };
