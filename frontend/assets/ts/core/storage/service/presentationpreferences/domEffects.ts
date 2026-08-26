/* SoAI - Presentation preference DOM effect application [frontend/assets/ts/core/storage/service/presentationpreferences/domEffects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ANIMATION_SPEED_ATTRIBUTE } from '@core/animations/speed.ts';
import { getBody, getDocumentElement } from '@core/environment/public.ts';
import { dispatchClockPreferenceChanged, readClockPreferenceState, writeClockPreferenceState } from '@core/storage/clockPreferences.ts';
import type { ThemeApplyOptions } from '@core/storage/service/types.ts';
import type { UiPreferences } from '@core/storage/types.ts';
import { applyAccentColor } from '@core/theme/accentColor.ts';
import { applySurfaceColor } from '@core/theme/surfaceColor.ts';
import { applyInterfaceScaleAttribute, dispatchInterfaceScaleChanged } from '@core/layout/interfaceScale.ts';

interface PresentationPreferenceDomEffects {
    bodyClass: (className: string, enabled: boolean) => void;
    setGlassDisabled: (disabled: boolean) => void;
    setAttr: (name: string, value: string) => void;
}

interface PresentationPreferenceDomEffectsInput {
    preferences: UiPreferences;
    includeHeaderAutoHideClass: boolean;
    headerAutoHideClassAfterAttributes?: boolean | undefined;
    dispatchClockChanged: boolean;
    applyTheme: (preference: string, options?: ThemeApplyOptions) => string;
    effects: PresentationPreferenceDomEffects;
    afterScrollTopActionClass?: (() => void) | undefined;
}

const applyPresentationPreferenceDomEffects = (inputArguments: PresentationPreferenceDomEffectsInput): void => {
    const preferences = inputArguments.preferences;
    writeClockPreferenceState(preferences, readClockPreferenceState(preferences));
    inputArguments.applyTheme(preferences.theme, { persist: false });
    applyAccentColor({ root: getDocumentElement(), body: getBody() }, preferences.accentColor);
    applySurfaceColor({ root: getDocumentElement(), body: getBody() }, preferences.surfaceColor);
    inputArguments.effects.bodyClass('reduce-motions', preferences.reduceMotions);
    if (inputArguments.includeHeaderAutoHideClass && inputArguments.headerAutoHideClassAfterAttributes !== true) {
        inputArguments.effects.bodyClass('header-auto-hide-disabled', !preferences.headerAutoHide);
    }
    inputArguments.effects.bodyClass('scroll-top-action-disabled', !preferences.showScrollToTopButton);
    if (inputArguments.afterScrollTopActionClass) {
        inputArguments.afterScrollTopActionClass();
    }
    inputArguments.effects.setGlassDisabled(!preferences.glassEnabled);
    inputArguments.effects.setAttr('data-page-animation', preferences.pageAnimation);
    inputArguments.effects.setAttr('data-modal-animation', preferences.modalAnimation);
    inputArguments.effects.setAttr('data-notification-animation', preferences.notificationAnimation);
    inputArguments.effects.setAttr(ANIMATION_SPEED_ATTRIBUTE, preferences.animationSpeed);
    const interfaceScaleChanged = applyInterfaceScaleAttribute(getDocumentElement(), preferences.interfaceScale, inputArguments.effects.setAttr);
    if (inputArguments.includeHeaderAutoHideClass && inputArguments.headerAutoHideClassAfterAttributes === true) {
        inputArguments.effects.bodyClass('header-auto-hide-disabled', !preferences.headerAutoHide);
    }
    if (inputArguments.dispatchClockChanged) {
        dispatchClockPreferenceChanged(readClockPreferenceState(preferences));
    }
    if (interfaceScaleChanged) {
        dispatchInterfaceScaleChanged(preferences.interfaceScale);
    }
};

export { applyPresentationPreferenceDomEffects };
export type { PresentationPreferenceDomEffectsInput, PresentationPreferenceDomEffects };
