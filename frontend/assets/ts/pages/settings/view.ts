/* SoAI - Settings page rendering [frontend/assets/ts/pages/settings/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import type { HeaderActionDefinition } from '@core/routing/pages/pagetypes/public.ts';

import { EMPTY_UI_HTML, uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import { SETTINGS_ACTION_SAVE, SETTINGS_ACTION_TOGGLE_ADVANCED_MODE } from '@pages/settings/actions.ts';
import { UI_IDS } from '@features/settings/public.ts';
import type { SettingsViewDependencies } from '@pages/settings/types.ts';

const buildAdvancedToggle = (dependencies: SettingsViewDependencies): TrustedHtml => {
    const label = dependencies.advancedMode ? i18n.t('settings.basicMode') : i18n.t('settings.advancedMode');
    const advancedIcon = dependencies.getIconSync('settings', { size: 24, strokeWidth: 1.5 });
    return uiHtml`<div class="advanced-toggle-container">
        <button type="button" id="${uiAttr(UI_IDS.ADVANCED_TOGGLE_BTN)}" data-action="${uiAttr(SETTINGS_ACTION_TOGGLE_ADVANCED_MODE)}" class="advanced-toggle-btn ui-button ui-variant-neutral" aria-label="${uiAttr(label)}" data-tooltip="${uiAttr(label)}">${advancedIcon}<span>${label}</span></button>
    </div>`;
};

const buildHeaderActions = (dependencies: SettingsViewDependencies): HeaderActionDefinition[] => {
    const actions: HeaderActionDefinition[] = [];
    const saveIcon = dependencies.getIconSync('save', { size: 24, strokeWidth: 1.5 });

    if (dependencies.canAccessAdvanced) {
        actions.push({
            type: 'custom',
            html: buildAdvancedToggle(dependencies)
        });
    }

    actions.push({ type: 'search' });
    const saveAriaLabel = i18n.t('settings.saveButtonAriaLabel');
    actions.push({
        type: 'custom',
        html: uiHtml`<button type="button" id="${uiAttr(UI_IDS.SAVE_BUTTON)}" data-action="${uiAttr(SETTINGS_ACTION_SAVE)}" class="ui-button ui-variant-accent save-btn" disabled aria-label="${uiAttr(saveAriaLabel)}" data-tooltip="${uiAttr(saveAriaLabel)}">${saveIcon}<span>${i18n.t('settings.saveButton')}</span></button>`
    });

    return actions;
};

const buildInitialContent = (): string => {
    return `<div id="${UI_IDS.CONTENT}">
        <div class="settings-loading" id="${UI_IDS.LOADING}">
            <div class="spinner"></div>
            <p>${i18n.t('settings.loadingSettings')}</p>
        </div>
    </div>`;
};

export const renderSettingsPageView = (dependencies: SettingsViewDependencies): TrustedHtml => {
    const header = dependencies.generateStandardHeader({
        title: dependencies.advancedMode && dependencies.canAccessAdvanced ? i18n.t('settings.advancedTitle') : i18n.t('settings.title'),
        description: i18n.t('settings.description'),
        floating: true,
        contentAreaClass: 'settings-content',
        actions: buildHeaderActions(dependencies),
        tabs: { containerId: UI_IDS.TAB_CONTAINER, html: EMPTY_UI_HTML },
        ariaLabel: i18n.t('settings.ariaLabel')
    });
    const contentHtml = header.html.replace('<!-- Page content goes here -->', buildInitialContent());
    return toTrustedUiHtml(contentHtml);
};
