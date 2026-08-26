/* SoAI - Frontend remote preference merge ownership [frontend/assets/ts/core/storage/persistence/mergeremotepreferences/mergeRemotePreferences.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dispatchCustomEvent } from '@core/environment/public.ts';
import { arraysEqual } from '@core/primitives/equality.ts';
import { clockPreferenceStatesEqual, dispatchClockPreferenceChanged, readClockPreferenceState } from '@core/storage/clockPreferences.ts';
import { CHANGED_EVENTS } from '@core/storage/service/constants.ts';
import { syncLocalizationPreferencesFromUi } from '@core/storage/localizationPreferences.ts';
import { parseStorageCache } from '@core/storage/persistence/storageCacheParsing.ts';
import { applyPresentationPreferenceDomEffects } from '@core/storage/service/presentationpreferences/domEffects.ts';
import type { MergeRemoteContext } from '@core/storage/persistence/mergeremotepreferences/types.ts';
import { normalizeAccentColorPreference } from '@core/theme/accentColor.ts';
import { normalizeSurfaceColorPreference } from '@core/theme/surfaceColor.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

const dispatch = (name: string, detail?: JsonObject): void => {
    dispatchCustomEvent(name, detail ?? null);
};

const mergeRemotePreferences = (context: MergeRemoteContext, remote: JsonValue | null | undefined): void => {
    if (!isJsonObject(remote)) {
        throw new Error('Remote preferences payload must be an object');
    }

    const oldLanguage = context.cache.ui.language;
    const oldHiddenSidebarPages = context.cache.ui.hiddenSidebarPages.slice();
    const oldShowMainStatusIndicator = context.cache.ui.showMainStatusIndicator;
    const oldCodeRecognitionEnabled = context.cache.ui.codeRecognitionEnabled;
    const oldClockPreferences = readClockPreferenceState(context.cache.ui);
    const merged = parseStorageCache(remote, {
        clone: context.clone,
        createDefaults: context.createDefaults,
        internalRemoteKeys: context.internalRemoteKeys,
        normalizeLimit: context.normalizeLimit,
        normalizeZoom: context.normalizeZoom,
        preserveDefaultMisc: true,
        rejectUnknownKeys: true
    });

    context.cache.ui = merged.ui;
    context.cache.logs = merged.logs;
    context.cache.terminal = merged.terminal;
    context.cache.search = merged.search;
    context.cache.hardware = merged.hardware;
    context.cache.filters = merged.filters;
    context.cache.wizard = merged.wizard;
    context.cache.settings = merged.settings;
    context.cache.misc = merged.misc;
    for (const group of context.persistedGroupKeys) {
        context.updatePersisted(group);
    }
    for (const group of context.localStorageGroups) {
        context.syncLocal(group);
    }

    const ui = context.cache.ui;
    syncLocalizationPreferencesFromUi(ui);
    ui.accentColor = normalizeAccentColorPreference(ui.accentColor) ?? null;
    ui.surfaceColor = normalizeSurfaceColorPreference(ui.surfaceColor) ?? null;
    applyPresentationPreferenceDomEffects({
        preferences: ui,
        includeHeaderAutoHideClass: true,
        headerAutoHideClassAfterAttributes: true,
        dispatchClockChanged: false,
        applyTheme: context.applyTheme,
        effects: {
            bodyClass: context.bodyClass,
            setGlassDisabled: context.setGlassDisabled,
            setAttr: context.setAttr
        }
    });
    context.ensureMainState();

    const newClockPreferences = readClockPreferenceState(ui);
    if (!clockPreferenceStatesEqual(oldClockPreferences, newClockPreferences)) {
        dispatchClockPreferenceChanged(newClockPreferences);
    }

    if (ui.showMainStatusIndicator !== oldShowMainStatusIndicator || !arraysEqual(ui.hiddenSidebarPages, oldHiddenSidebarPages)) {
        dispatch(CHANGED_EVENTS.sidebarCustomization);
    }

    if (ui.codeRecognitionEnabled !== oldCodeRecognitionEnabled) {
        dispatch(CHANGED_EVENTS.codeRecognition, { enabled: ui.codeRecognitionEnabled });
    }

    if (ui.language !== oldLanguage) {
        dispatch('soai:language:changed', { language: ui.language });
    }
};

export { mergeRemotePreferences };
export type { MergeRemoteContext };
