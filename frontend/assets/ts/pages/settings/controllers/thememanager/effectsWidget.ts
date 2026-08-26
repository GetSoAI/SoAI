/* SoAI - Settings page effects widget [frontend/assets/ts/pages/settings/controllers/thememanager/effectsWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isAnimationSpeed } from '@core/animations/speed.ts';
import { i18n } from '@core/i18n/index.ts';
import { createSettingsUiPreferenceFieldKey } from '@core/settings/settingsFieldKeys.ts';
import { renderSelectControl, renderSettingItem, renderSettingsGroup, renderSettingsSubgroup, renderToggleControl } from '@core/settings/settingsMarkup.ts';
import type { ThemeViewContext } from '@pages/settings/controllers/thememanager/contracts.ts';

const renderEffectsSubgroup = (context: ThemeViewContext): string => {
    const { host, getPreferenceStateLabels } = context;
    const disableAnimationsValue = host.getUiPrefValue('reduceMotions');
    if (typeof disableAnimationsValue !== 'boolean') {
        throw new TypeError('uiPrefs.reduceMotions must be a boolean');
    }
    const glassEnabledValue = host.getUiPrefValue('glassEnabled');
    if (typeof glassEnabledValue !== 'boolean') {
        throw new TypeError('uiPrefs.glassEnabled must be a boolean');
    }
    const headerAutoHideValue = host.getUiPrefValue('headerAutoHide');
    if (typeof headerAutoHideValue !== 'boolean') {
        throw new TypeError('uiPrefs.headerAutoHide must be a boolean');
    }
    const showScrollToTopButtonValue = host.getUiPrefValue('showScrollToTopButton');
    if (typeof showScrollToTopButtonValue !== 'boolean') {
        throw new TypeError('uiPrefs.showScrollToTopButton must be a boolean');
    }
    const pageAnimationValue = host.getUiPrefValue('pageAnimation');
    if (typeof pageAnimationValue !== 'string' || !pageAnimationValue.trim()) {
        throw new TypeError('uiPrefs.pageAnimation must be a non-empty string');
    }
    const modalAnimationValue = host.getUiPrefValue('modalAnimation');
    if (typeof modalAnimationValue !== 'string' || !modalAnimationValue.trim()) {
        throw new TypeError('uiPrefs.modalAnimation must be a non-empty string');
    }
    const notificationAnimationValue = host.getUiPrefValue('notificationAnimation');
    if (typeof notificationAnimationValue !== 'string' || !notificationAnimationValue.trim()) {
        throw new TypeError('uiPrefs.notificationAnimation must be a non-empty string');
    }
    const animationSpeedValue = host.getUiPrefValue('animationSpeed');
    if (!isAnimationSpeed(animationSpeedValue)) {
        throw new TypeError('uiPrefs.animationSpeed must be a valid animation speed');
    }
    const preferenceLabels = getPreferenceStateLabels();
    const animationOptions = [
        { value: 'fade', label: i18n.t('settings.effects.animations.options.fade') },
        { value: 'slide', label: i18n.t('settings.effects.animations.options.slide') },
        { value: 'scale', label: i18n.t('settings.effects.animations.options.scale') },
        { value: 'zoom', label: i18n.t('settings.effects.animations.options.zoom') },
        { value: 'lateral', label: i18n.t('settings.effects.animations.options.lateral') }
    ];
    const animationSpeedOptions = [
        { value: 'normal', label: i18n.t('settings.effects.animations.speedOptions.normal') },
        { value: 'fast', label: i18n.t('settings.effects.animations.speedOptions.fast') }
    ];

    return renderSettingsSubgroup({
        title: i18n.t('settings.effects.subgroupTitle'),
        description: i18n.t('settings.effects.subgroupDescription'),
        content: renderSettingsGroup([
            renderSettingItem({
                label: i18n.t('settings.effects.disableAnimations.label'),
                help: i18n.t('settings.effects.disableAnimations.help'),
                fieldKey: createSettingsUiPreferenceFieldKey('reduceMotions'),
                control: renderToggleControl({
                    id: 'disable-animations-toggle',
                    checked: disableAnimationsValue,
                    labels: preferenceLabels
                })
            }),
            renderSettingItem({
                label: i18n.t('settings.effects.header.autoHide.label'),
                help: i18n.t('settings.effects.header.autoHide.help'),
                fieldKey: createSettingsUiPreferenceFieldKey('headerAutoHide'),
                control: renderToggleControl({
                    id: 'header-auto-hide-toggle',
                    checked: headerAutoHideValue,
                    labels: preferenceLabels
                })
            }),
            renderSettingItem({
                label: i18n.t('settings.effects.glassEffects.label'),
                help: i18n.t('settings.effects.glassEffects.help'),
                fieldKey: createSettingsUiPreferenceFieldKey('glassEnabled'),
                control: renderToggleControl({
                    id: 'glass-effects-toggle',
                    checked: glassEnabledValue,
                    labels: preferenceLabels
                })
            }),
            renderSettingItem({
                label: i18n.t('settings.effects.scrollToTopButton.label'),
                help: i18n.t('settings.effects.scrollToTopButton.help'),
                fieldKey: createSettingsUiPreferenceFieldKey('showScrollToTopButton'),
                control: renderToggleControl({
                    id: 'scroll-to-top-button-toggle',
                    checked: showScrollToTopButtonValue,
                    labels: preferenceLabels
                })
            }),
            `<div id="animation-options-panel" class="settings-group animation-options-grid${disableAnimationsValue ? ' u-hidden' : ''}">
                    ${renderSettingItem({
                        label: i18n.t('settings.effects.animations.pageTransition.label'),
                        help: i18n.t('settings.effects.animations.pageTransition.help'),
                        fieldKey: createSettingsUiPreferenceFieldKey('pageAnimation'),
                        control: renderSelectControl({
                            id: 'page-animation-select',
                            options: animationOptions,
                            selected: pageAnimationValue
                        })
                    })}
                    ${renderSettingItem({
                        label: i18n.t('settings.effects.animations.modalAnimation.label'),
                        help: i18n.t('settings.effects.animations.modalAnimation.help'),
                        fieldKey: createSettingsUiPreferenceFieldKey('modalAnimation'),
                        control: renderSelectControl({
                            id: 'modal-animation-select',
                            options: animationOptions,
                            selected: modalAnimationValue
                        })
                    })}
                    ${renderSettingItem({
                        label: i18n.t('settings.effects.animations.notificationAnimation.label'),
                        help: i18n.t('settings.effects.animations.notificationAnimation.help'),
                        fieldKey: createSettingsUiPreferenceFieldKey('notificationAnimation'),
                        control: renderSelectControl({
                            id: 'notification-animation-select',
                            options: animationOptions,
                            selected: notificationAnimationValue
                        })
                    })}
                    ${renderSettingItem({
                        label: i18n.t('settings.effects.animations.speed.label'),
                        help: i18n.t('settings.effects.animations.speed.help'),
                        fieldKey: createSettingsUiPreferenceFieldKey('animationSpeed'),
                        control: renderSelectControl({
                            id: 'animation-speed-select',
                            options: animationSpeedOptions,
                            selected: animationSpeedValue
                        })
                    })}
            </div>`
        ])
    });
};

export { renderEffectsSubgroup };
