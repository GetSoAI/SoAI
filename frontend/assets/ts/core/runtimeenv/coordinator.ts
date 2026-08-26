/* SoAI - Shared runtime environment coordinator [frontend/assets/ts/core/runtimeenv/coordinator.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getBroadcastChannelCtor } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { isFunction, isObject, isString } from '@core/typeGuards.ts';
import { LOG_TAG_DETACHED } from '@core/runtimeenv/constants.ts';
import { isBroadcastChannelInterface } from '@core/runtimeenv/guards.ts';
import type { BroadcastChannelInterface, CoordinatorMessage } from '@core/runtimeenv/internalContracts.ts';
import { ensureError } from '@core/errors/coerce.ts';

type MessageHandler = (message: CoordinatorMessage) => void;

class DetachedWindowCoordinator {
    channelName: string;
    windowId: string;
    listeners: Map<string, Set<MessageHandler>>;
    channel: BroadcastChannelInterface | null;

    constructor(windowId: string) {
        this.channelName = 'soai.detached.windows';
        if (!isValidStr(windowId)) throw new Error('Detached window coordinator requires a window identity');
        this.windowId = trimStr(windowId);
        this.listeners = new Map();
        this.channel = this.#createChannel();
    }

    #createChannel(): BroadcastChannelInterface | null {
        let channel: BroadcastChannelInterface;
        try {
            const BroadcastChannelCtor = getBroadcastChannelCtor();
            channel = new BroadcastChannelCtor(this.channelName);
        } catch (error) {
            errorHandler.warn(LOG_TAG_DETACHED, 'BroadcastChannel constructor is unavailable', ensureError(error));
            return null;
        }
        if (!isBroadcastChannelInterface(channel)) {
            errorHandler.warn(LOG_TAG_DETACHED, 'BroadcastChannel implementation is unavailable', { channelType: typeof channel });
            return null;
        }
        const handleMessage = (event: MessageEvent): void => {
            if (!isObject(event) || !('data' in event)) {
                errorHandler.warn(LOG_TAG_DETACHED, 'Received malformed BroadcastChannel event', { event });
                return;
            }
            this.#handleMessage(event.data);
        };
        if (isFunction(channel.addEventListener)) {
            channel.addEventListener('message', handleMessage);
            return channel;
        }
        channel.onmessage = handleMessage;
        return channel;
    }

    #handleMessage(message: JsonValue): void {
        if (!isObject(message)) {
            errorHandler.warn(LOG_TAG_DETACHED, 'Received non-object message payload', { payload: message });
            return;
        }
        const messagePayload = message;
        const typeValue = messagePayload['type'] ?? null;
        const sourceValue = messagePayload['source'] ?? null;
        const targetValue = messagePayload['target'] ?? null;
        if (!isValidStr(typeValue)) {
            errorHandler.warn(LOG_TAG_DETACHED, 'Message missing required type', { payload: messagePayload });
            return;
        }
        if (!isValidStr(sourceValue)) {
            errorHandler.warn(LOG_TAG_DETACHED, 'Message missing required source', { payload: messagePayload });
            return;
        }
        if (!isValidStr(targetValue)) {
            errorHandler.warn(LOG_TAG_DETACHED, 'Message missing required target', { payload: messagePayload });
            return;
        }
        if (sourceValue === this.windowId) return;
        if (targetValue !== this.windowId && targetValue !== 'broadcast') return;

        const messageType = typeValue;
        const payloadValue = isObject(messagePayload['payload']) ? messagePayload['payload'] : null;
        const coordinatorMessage: CoordinatorMessage = {
            type: typeValue,
            source: sourceValue,
            target: targetValue,
            ...(payloadValue ? { payload: payloadValue } : {})
        };
        const registry = this.listeners.get(messageType);
        if (registry) {
            registry.forEach((handler) => {
                if (!isFunction(handler)) {
                    errorHandler.warn(LOG_TAG_DETACHED, 'Registered listener is not a function', {
                        type: messageType
                    });
                    return;
                }
                try {
                    handler(coordinatorMessage);
                } catch (error) {
                    const runtimeError = ensureError(error);
                    errorHandler.warn(LOG_TAG_DETACHED, 'Listener execution failed', runtimeError);
                }
            });
        }
    }

    on(type: string, handler: MessageHandler): () => void {
        if (!isValidStr(type)) throw new Error('Detached window coordinator requires a message type');
        if (!isFunction(handler)) throw new Error('Detached window coordinator requires a handler function');
        const key = trimStr(type);
        if (!this.listeners.has(key)) this.listeners.set(key, new Set());
        const registry = this.listeners.get(key);
        if (!registry) {
            throw new Error(`Detached window coordinator failed to create listener registry for "${key}"`);
        }
        registry.add(handler);
        return () => {
            registry.delete(handler);
        };
    }

    send(type: string, payload: JsonObject = {}, target: string = 'broadcast'): boolean {
        if (!isValidStr(type)) throw new Error('Detached window coordinator requires a message type');
        if (!isObject(payload)) throw new Error('Detached window coordinator payload must be an object');
        if (!isValidStr(target)) throw new Error('Detached window coordinator requires a target identifier');
        if (this.channel === null) {
            errorHandler.warn(LOG_TAG_DETACHED, 'Message dispatch skipped because BroadcastChannel is unavailable', { type: trimStr(type), target: trimStr(target) });
            return false;
        }
        try {
            this.channel.postMessage({
                type: trimStr(type),
                payload,
                source: this.windowId,
                target: trimStr(target)
            });
            return true;
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.warn(LOG_TAG_DETACHED, 'Message dispatch failed', runtimeError);
            throw ensureError(error);
        }
    }

    destroy(): void {
        this.listeners.clear();
        this.channel?.close();
    }
}

const isValidStr = (value: JsonValue): value is string => isString(value) && Boolean(value.trim());
const trimStr = (value: string): string => value.trim();

export { DetachedWindowCoordinator };
