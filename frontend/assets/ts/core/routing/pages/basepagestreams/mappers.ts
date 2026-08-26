/* SoAI - Shared frontend routing pages base page streams mapping [frontend/assets/ts/core/routing/pages/basepagestreams/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasFunctionProperty, hasOwn, isArray, isObject, isString } from '@core/typeGuards.ts';
import { i18n } from '@core/i18n/index.ts';
import type { BasePageStreamsAutoResourceResult, EnsureReadyStreamManager, OperationsSubscriptionManager, PageAutoResourceState, VerifiableSubscriptionManager } from '@core/routing/pages/basepagestreams/internalContracts.ts';
import type { AutoResourceState } from '@core/realtime/streammanager/types.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

const isEnsureReadyStreamManager = (candidate: EnsureReadyStreamManager | JsonValue | null | undefined): candidate is EnsureReadyStreamManager => {
    if (!isObject(candidate)) {
        return false;
    }
    return hasFunctionProperty(candidate, 'ensureReady');
};

const isOperationsSubscriptionManager = (candidate: OperationsSubscriptionManager | JsonValue | null | undefined): candidate is OperationsSubscriptionManager => {
    if (!isObject(candidate)) {
        return false;
    }
    return hasFunctionProperty(candidate, 'subscribeOperations');
};

const isVerifiableSubscriptionManager = (candidate: VerifiableSubscriptionManager | JsonValue | null | undefined): candidate is VerifiableSubscriptionManager => {
    if (!isObject(candidate)) {
        return false;
    }
    return hasFunctionProperty(candidate, 'verifyReady');
};

const toPageAutoResourceState = (value: JsonValue | PageAutoResourceState | AutoResourceState | null | undefined): PageAutoResourceState | null => {
    if (!isObject(value) || isArray(value)) {
        return null;
    }
    const statusValue = value['status'];
    if (!isString(statusValue)) {
        return null;
    }
    if (statusValue !== 'offline' && statusValue !== 'ready' && statusValue !== 'error') {
        return null;
    }
    const errorValue = value['error'];
    const errorRecord = isObject(errorValue) && !isArray(errorValue) ? errorValue : null;
    const baseUrlValue = errorRecord && hasOwn(errorRecord, 'baseUrl') && 'baseUrl' in errorRecord ? errorRecord.baseUrl : null;
    const messageValue = errorRecord && hasOwn(errorRecord, 'message') && 'message' in errorRecord ? errorRecord.message : null;
    const error =
        baseUrlValue || messageValue
            ? {
                  ...(isString(baseUrlValue) ? { baseUrl: baseUrlValue } : {}),
                  ...(isString(messageValue) ? { message: messageValue } : {})
              }
            : undefined;
    return { status: statusValue, ...(error ? { error } : {}) };
};

const evaluateAutoResourceBannerState = (value: JsonValue | PageAutoResourceState | AutoResourceState | null | undefined, isOfflineVisible: boolean): BasePageStreamsAutoResourceResult => {
    const state = toPageAutoResourceState(value);
    if (!state) {
        return {
            state: null,
            shouldShowOfflineBanner: false,
            shouldClearOfflineBanner: false,
            message: null
        };
    }
    if (state.status === 'offline') {
        return {
            state,
            shouldShowOfflineBanner: !isOfflineVisible,
            shouldClearOfflineBanner: false,
            message: i18n.t('collections.offline.banner')
        };
    }
    if (state.status === 'ready') {
        return {
            state,
            shouldShowOfflineBanner: false,
            shouldClearOfflineBanner: isOfflineVisible,
            message: null
        };
    }
    return {
        state,
        shouldShowOfflineBanner: false,
        shouldClearOfflineBanner: false,
        message: null
    };
};

export { evaluateAutoResourceBannerState, isEnsureReadyStreamManager, isOperationsSubscriptionManager, isVerifiableSubscriptionManager };
