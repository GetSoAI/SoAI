/* SoAI - Shared storage service actions [frontend/assets/ts/core/storage/service/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { dispatchCustomEvent } from '@core/environment/public.ts';
import { EVENT_REQUEST } from '@core/languageservice/constants.ts';
import { toJsonCompatibleValue } from '@core/primitives/clone.ts';
import { isSafeRedirectPath } from '@core/storage/redirects.ts';
import { CHAT_PREFERENCE_LIMIT, CHANGED_EVENTS } from '@core/storage/service/constants.ts';
import { syncLocalizationPreferences } from '@core/storage/service/localizationpreferences/actions.ts';
import { normalizeNonBlankStringOrNull, normalizeSessionData } from '@core/storage/normalization.ts';
import type { StorageRuntime } from '@core/storage/service/types.ts';
import { isImageFitType } from '@core/storage/guards.ts';
import type { ClockFormatType, ImageFitType, SessionData } from '@core/storage/types.ts';
import { isNumber, isObject, isString } from '@core/typeGuards.ts';
import { applyChatPreferencesPatch, applyHardwarePreferencesPatch, collectList } from '@core/storage/service/mappers.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

const dispatch = (name: string, detail?: JsonObject): void => {
    dispatchCustomEvent(name, detail ?? null);
};

const trimQuery = (query: string): string => (query || '').trim();

const createStorageStateActions = (
    core: StorageRuntime
): {
    setChatPreferences: (patch: JsonValue) => void;
    setChatTextZoom: (value: number) => void;
    addRecentSearch: (query: string) => string[];
    clearRecentSearches: () => void;
    setHardwarePreferences: (patch: JsonValue) => void;
    saveGPUSettings: (id: string, settings: JsonValue) => void;
    setSession: (patch: Partial<SessionData>) => void;
    clearSession: () => void;
    setRedirectAfterLogin: (path: string | null) => void;
    clearRedirectAfterLogin: () => void;
    setWizardCompletionPending: (value: boolean) => void;
    setWizardCompleted: () => Promise<void>;
    setClockFormat: (format: ClockFormatType) => void;
    setLanguage: (language: string) => void;
    setHiddenSidebarPages: (pages: string[]) => void;
    setShowMainStatusIndicator: (show: boolean) => void;
    setHiddenDashboardElements: (elements: string[]) => void;
    setDashboardLocked: (locked: boolean) => void;
    setDashboardImageCard: (value: string | null) => void;
    setDashboardImageCardFit: (fit: ImageFitType) => void;
    setDashboardMemo: (value: string | null) => void;
    setDefaultPage: (value: string | null) => void;
    setPromptEnhancerModel: (value: string | null) => void;
    setLogsPreferences: (patch: JsonValue) => void;
    setLogLineLimit: (limit: number) => void;
    setLogsTextZoom: (zoom: number) => void;
} => {
    const state = core.state;

    const setChatPreferences = (patch: JsonValue): void => {
        if (!isObject(patch)) {
            return;
        }

        applyChatPreferencesPatch(state, patch);
        terminateHandledPromise(core.queuePersist('chat'));
    };

    const setChatTextZoom = (value: number): void => {
        const normalized = core.normalizeZoom(value, 0.5, 1.5);
        if (normalized !== state.cache.chat.textZoom) {
            state.cache.chat.textZoom = normalized;
            terminateHandledPromise(core.queuePersist('chat'));
        }
    };

    const addRecentSearch = (query: string): string[] => {
        if (!trimQuery(query)) {
            return state.cache.search.recent.slice();
        }
        const list = state.cache.search.recent.filter((entry) => entry !== query);
        list.unshift(query);
        state.cache.search.recent = list.slice(0, CHAT_PREFERENCE_LIMIT);
        terminateHandledPromise(core.queuePersist('search'));
        return state.cache.search.recent.slice();
    };

    const clearRecentSearches = (): void => {
        state.cache.search.recent = [];
        terminateHandledPromise(core.queuePersist('search'));
    };

    const setHardwarePreferences = (patch: JsonValue): void => {
        applyHardwarePreferencesPatch(state, patch);
        terminateHandledPromise(core.queuePersist('hardware'));
    };

    const saveGPUSettings = (id: string, settings: JsonValue): void => {
        if (!id) {
            throw new Error('GPU id is required');
        }
        state.cache.hardware.gpuSettings[id] = toJsonCompatibleValue(settings);
        terminateHandledPromise(core.queuePersist('hardware'));
    };

    const setSession = (patch: Partial<SessionData>): void => {
        if (!isObject(patch)) {
            return;
        }
        const previousUserId = state.session['userId'];
        const nextSession = normalizeSessionData(toJsonCompatibleValue({ ...state.session, ...patch }));
        if (nextSession['userId'] !== previousUserId) {
            state.pendingGroups.clear();
            state.persistedChecksums = {};
            state.inflightChecksums = {};
            state.queuedChecksums = {};
        }
        state.session = nextSession;
        core.writeStorage('sessionStorage', state.localKeys.session, toJsonCompatibleValue(state.session));
        core.scheduleBroadcast();
    };

    const clearSession = (): void => {
        state.session = {};
        state.pendingGroups.clear();
        state.persistedChecksums = {};
        state.inflightChecksums = {};
        state.queuedChecksums = {};
        core.writeStorage('sessionStorage', state.localKeys.session, toJsonCompatibleValue(state.session));
        core.scheduleBroadcast();
    };

    const setRedirectAfterLogin = (path: string | null): void => {
        if (path !== null && path !== undefined) {
            if (!isString(path) || !isSafeRedirectPath(path)) {
                throw new Error('redirect_after_login must be a safe absolute path');
            }
            state.redirectAfterLogin = path;
        } else {
            state.redirectAfterLogin = null;
        }
        const redirectAfterLogin = state.redirectAfterLogin || null;
        if (redirectAfterLogin === null) {
            delete state.session['redirect_after_login'];
        } else {
            state.session['redirect_after_login'] = redirectAfterLogin;
        }
        core.writeStorage('sessionStorage', state.localKeys.session, toJsonCompatibleValue(state.session));
        core.scheduleBroadcast();
    };

    const clearRedirectAfterLogin = (): void => {
        state.redirectAfterLogin = null;
        delete state.session['redirect_after_login'];
        core.writeStorage('sessionStorage', state.localKeys.session, toJsonCompatibleValue(state.session));
        core.scheduleBroadcast();
    };

    const setWizardCompletionPending = (value: boolean): void => {
        if (value === true) {
            state.session['wizard_completion_pending'] = true;
        } else {
            delete state.session['wizard_completion_pending'];
        }
        core.writeStorage('sessionStorage', state.localKeys.session, toJsonCompatibleValue(state.session));
        core.scheduleBroadcast();
    };

    const setWizardCompleted = async (): Promise<void> => {
        state.cache.wizard.completed = true;
        delete state.session['wizard_completion_pending'];
        core.writeStorage('sessionStorage', state.localKeys.session, toJsonCompatibleValue(state.session));
        core.scheduleBroadcast();
        await core.queuePersist('wizard');
    };

    const setClockFormat = (format: ClockFormatType): void => {
        if (format === state.cache.ui.clockFormat) {
            return;
        }
        state.cache.ui.clockFormat = format;
        syncLocalizationPreferences(core);
        terminateHandledPromise(core.queuePersist('ui'));
    };

    const setLanguage = (language: string): void => {
        const normalizedLanguage = String(language).trim();
        if (!normalizedLanguage) {
            throw new TypeError('language must be a non-empty string');
        }
        if (normalizedLanguage === state.cache.ui.language) {
            return;
        }
        state.cache.ui.language = normalizedLanguage;
        syncLocalizationPreferences(core);
        terminateHandledPromise(core.queuePersist('ui'));
        dispatch(EVENT_REQUEST, { language: normalizedLanguage });
    };

    const setHiddenSidebarPages = (pages: string[]): void => {
        state.cache.ui.hiddenSidebarPages = collectList(pages);
        terminateHandledPromise(core.queuePersist('ui'));
        dispatch(CHANGED_EVENTS.sidebarCustomization);
    };

    const setShowMainStatusIndicator = (show: boolean): void => {
        state.cache.ui.showMainStatusIndicator = !!show;
        state.cache.ui.mainStatePreferenceVersion = 1;
        terminateHandledPromise(core.queuePersist('ui'));
        dispatch(CHANGED_EVENTS.sidebarCustomization);
    };

    const setHiddenDashboardElements = (elements: string[]): void => {
        state.cache.ui.hiddenDashboardElements = collectList(elements);
        terminateHandledPromise(core.queuePersist('ui'));
        dispatch(CHANGED_EVENTS.dashboardCustomization);
    };

    const setDashboardLocked = (locked: boolean): void => {
        state.cache.ui.dashboardLocked = !!locked;
        terminateHandledPromise(core.queuePersist('ui'));
        dispatch(CHANGED_EVENTS.dashboardCustomization);
    };

    const setDashboardImageCard = (value: string | null): void => {
        state.cache.ui.dashboardImageCard = value ?? null;
        terminateHandledPromise(core.queuePersist('ui'));
        dispatch(CHANGED_EVENTS.dashboardCustomization);
    };

    const setDashboardImageCardFit = (fit: ImageFitType): void => {
        if (!isImageFitType(fit)) {
            throw new Error('dashboard_image_card_fit must be contain or cover');
        }
        state.cache.ui.dashboardImageCardFit = fit;
        terminateHandledPromise(core.queuePersist('ui'));
        dispatch(CHANGED_EVENTS.dashboardCustomization);
    };

    const setDashboardMemo = (value: string | null): void => {
        state.cache.ui.dashboardMemo = normalizeNonBlankStringOrNull(value);
        terminateHandledPromise(core.queuePersist('ui'));
        dispatch(CHANGED_EVENTS.dashboardCustomization);
    };

    const setDefaultPage = (value: string | null): void => {
        state.cache.ui.defaultPage = normalizeNonBlankStringOrNull(value);
        terminateHandledPromise(core.queuePersist('ui'));
    };

    const setPromptEnhancerModel = (value: string | null): void => {
        state.cache.ui.promptEnhancerModel = typeof value === 'string' && value.trim() ? value.trim() : null;
        terminateHandledPromise(core.queuePersist('ui'));
    };

    const setLogsPreferences = (patch: JsonValue): void => {
        if (!isObject(patch)) {
            return;
        }
        const lineLimit = patch['line_limit'];
        if (isNumber(lineLimit) && Number.isFinite(lineLimit)) {
            state.cache.logs.lineLimit = core.normalizeLimit(lineLimit);
        }
        const textZoom = patch['text_zoom'];
        if (isNumber(textZoom) && Number.isFinite(textZoom)) {
            state.cache.logs.textZoom = core.normalizeZoom(textZoom, 0.5, 2);
        }
        terminateHandledPromise(core.queuePersist('logs'));
    };

    const setLogLineLimit = (limit: number): void => {
        const normalized = core.normalizeLimit(limit);
        if (normalized !== state.cache.logs.lineLimit) {
            state.cache.logs.lineLimit = normalized;
            terminateHandledPromise(core.queuePersist('logs'));
        }
    };

    const setLogsTextZoom = (zoom: number): void => {
        const normalized = core.normalizeZoom(zoom, 0.5, 2);
        if (normalized !== state.cache.logs.textZoom) {
            state.cache.logs.textZoom = normalized;
            terminateHandledPromise(core.queuePersist('logs'));
        }
    };

    return {
        setChatPreferences,
        setChatTextZoom,
        addRecentSearch,
        clearRecentSearches,
        setHardwarePreferences,
        saveGPUSettings,
        setSession,
        clearSession,
        setRedirectAfterLogin,
        clearRedirectAfterLogin,
        setWizardCompletionPending,
        setWizardCompleted,
        setClockFormat,
        setLanguage,
        setHiddenSidebarPages,
        setShowMainStatusIndicator,
        setHiddenDashboardElements,
        setDashboardLocked,
        setDashboardImageCard,
        setDashboardImageCardFit,
        setDashboardMemo,
        setDefaultPage,
        setPromptEnhancerModel,
        setLogsPreferences,
        setLogLineLimit,
        setLogsTextZoom
    };
};

export { createStorageStateActions };
