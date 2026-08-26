/* SoAI - Environment guards for chat render worker pools [frontend/assets/ts/features/chat/messagerenderworker/workerPoolEnvironment.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isObject, isString } from '@core/typeGuards.ts';
import type { RenderContext, WorkerReadyMessage, WorkerResponse } from '@features/chat/messagerenderworker/protocol.ts';

const requireModernWorkerSupport = (): void => {
    if (typeof Worker !== 'function') {
        throw new Error('Chat requires Worker support');
    }
    const cores = navigator.hardwareConcurrency;
    if (typeof cores !== 'number' || !Number.isFinite(cores) || cores <= 0) {
        throw new Error('Chat requires navigator.hardwareConcurrency');
    }
    if (!globalThis.crypto || typeof globalThis.crypto.getRandomValues !== 'function') {
        throw new Error('Chat requires crypto.getRandomValues');
    }
};

const computeWorkerCount = (): number => {
    const cores = navigator.hardwareConcurrency;
    const usable = Math.max(1, Math.floor(cores) - 2);
    return Math.min(6, usable);
};

const isWorkerReadyMessage = <T>(value: T): value is T & WorkerReadyMessage => isObject(value) && 'type' in value && value.type === 'ready';

const isRenderContext = <T>(value: T): value is T & RenderContext => {
    if (!isObject(value)) {
        return false;
    }
    if (!('epoch' in value) || !('conversationId' in value) || !('messageDomId' in value) || !('messageRevision' in value) || !('stateSignature' in value)) {
        return false;
    }
    return typeof value.epoch === 'number' && Number.isFinite(value.epoch) && isString(value.conversationId) && isString(value.messageDomId) && typeof value.messageRevision === 'number' && Number.isFinite(value.messageRevision) && isString(value.stateSignature);
};

const isWorkerResponse = <T>(value: T): value is T & WorkerResponse => {
    if (!isObject(value)) {
        return false;
    }
    if (!('type' in value) || !('requestId' in value)) {
        return false;
    }
    if (!isString(value.type) || !isString(value.requestId)) {
        return false;
    }
    if (value.type === 'rendered') {
        if (!('html' in value) || !('context' in value)) {
            return false;
        }
        return isString(value.html) && isRenderContext(value.context);
    }
    if (value.type === 'ok') {
        return true;
    }
    if (value.type === 'error') {
        if (!('message' in value)) {
            return false;
        }
        return isString(value.message);
    }
    return false;
};

export { computeWorkerCount, isWorkerReadyMessage, isWorkerResponse, requireModernWorkerSupport };
