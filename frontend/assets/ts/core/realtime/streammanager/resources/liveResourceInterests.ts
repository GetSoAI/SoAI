/* SoAI - Shared realtime live resource interests [frontend/assets/ts/core/realtime/streammanager/resources/liveResourceInterests.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { HARDWARE, HARDWARE_PROCESSES, METRICS, MODELS_LAST_USED, PLUGINS_LAST_USED, POWER_OPERATIONS, WEBUI_CHAT_ACTIVITY, WEBUI_CHAT_PRESENTATION } from '@core/realtime/streammanager/resources/ids.ts';
import { arraysEqual } from '@core/primitives/equality.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { isNonNegativeInteger, isString } from '@core/typeGuards.ts';
import { WEBSOCKET_EVENT_TYPES, WEBSOCKET_MESSAGE_TYPES } from '@core/websocketEvents.ts';

type LiveResourceInterestChange = {
    token: string | null;
    changed: boolean;
};

type LiveResourceInterestServerOutcome = { type: 'acknowledged' | 'rejected'; resources: string[]; generation: number } | { type: 'ignored'; resources: string[] };

const RESOURCE_INTEREST_REJECTION_REASONS = new Set(['malformed', 'unknown_resource', 'unknown_conversation', 'forbidden', 'stale_generation', 'generation_conflict']);

const isLiveResourceInterest = (resource: string): boolean => resource === METRICS || resource === HARDWARE || resource === HARDWARE_PROCESSES || resource === POWER_OPERATIONS || resource === WEBUI_CHAT_ACTIVITY || resource === WEBUI_CHAT_PRESENTATION || resource === MODELS_LAST_USED || resource === PLUGINS_LAST_USED;

class LiveResourceInterestState {
    readonly #resourceByToken = new Map<string, string>();
    #generation = 0;
    #sequence = 0;
    #chatPresentationConversationId: string | null = null;

    acquire(resource: string): LiveResourceInterestChange {
        if (!isLiveResourceInterest(resource) || resource === WEBUI_CHAT_PRESENTATION) return { token: null, changed: false };
        const token = `live-resource-${++this.#sequence}`;
        const hadInterest = [...this.#resourceByToken.values()].includes(resource);
        this.#resourceByToken.set(token, resource);
        const changed = !hadInterest;
        if (changed) this.#generation += 1;
        return { token, changed };
    }

    acquireChatPresentation(conversationId: string): LiveResourceInterestChange {
        const normalizedConversationId = conversationId.trim();
        if (!normalizedConversationId || normalizedConversationId !== conversationId || this.#chatPresentationConversationId !== null) {
            return { token: null, changed: false };
        }
        const token = `live-resource-${++this.#sequence}`;
        this.#resourceByToken.set(token, WEBUI_CHAT_PRESENTATION);
        this.#chatPresentationConversationId = normalizedConversationId;
        this.#generation += 1;
        return { token, changed: true };
    }

    updateChatPresentation(token: string | null, conversationId: string): boolean {
        const normalizedConversationId = conversationId.trim();
        if (!token || this.#resourceByToken.get(token) !== WEBUI_CHAT_PRESENTATION || !normalizedConversationId || normalizedConversationId !== conversationId) {
            throw new Error('Invalid chat presentation interest update');
        }
        if (this.#chatPresentationConversationId === normalizedConversationId) return false;
        this.#chatPresentationConversationId = normalizedConversationId;
        this.#generation += 1;
        return true;
    }

    chatPresentationGeneration(token: string, conversationId: string): number | null {
        return this.#resourceByToken.get(token) === WEBUI_CHAT_PRESENTATION && this.#chatPresentationConversationId === conversationId ? this.#generation : null;
    }

    release(token: string | null): boolean {
        if (!token) return false;
        const resource = this.#resourceByToken.get(token);
        if (!resource) return false;
        this.#resourceByToken.delete(token);
        if (resource === WEBUI_CHAT_PRESENTATION) {
            this.#chatPresentationConversationId = null;
            this.#generation += 1;
            return true;
        }
        if ([...this.#resourceByToken.values()].includes(resource)) return false;
        this.#generation += 1;
        return true;
    }

    buildMessage(): JsonObject {
        return {
            type: WEBSOCKET_MESSAGE_TYPES.SET_RESOURCE_INTERESTS,
            generation: this.#generation,
            resources: this.#resources(),
            'chat_presentation_conversation_id': this.#chatPresentationConversationId
        };
    }

    parseServerEvent(eventType: string, payload: JsonValue): LiveResourceInterestServerOutcome {
        if (!isJsonObject(payload)) throw new Error('Invalid resource interest protocol payload');
        const protocolPayload = eventType === WEBSOCKET_EVENT_TYPES.INVALID_RESOURCE_INTEREST ? this.#readErrorDetails(payload) : payload;
        const generation = protocolPayload['generation'];
        if (!isNonNegativeInteger(generation)) throw new Error('Invalid resource interest protocol generation');
        const demandedResources = this.#resources();
        if (eventType === WEBSOCKET_EVENT_TYPES.RESOURCE_INTERESTS_APPLIED) {
            if (generation < this.#generation) return { type: 'ignored', resources: [] };
            if (generation > this.#generation) throw new Error('Invalid resource interest protocol future generation');
            const resources = this.#readResources(protocolPayload['resources']);
            if (!arraysEqual(resources, demandedResources)) throw new Error('Invalid resource interest protocol acknowledgement resources');
            const selector = this.#readChatPresentationSelector(protocolPayload['chat_presentation_conversation_id'], resources);
            if (selector !== this.#chatPresentationConversationId) throw new Error('Invalid resource interest protocol acknowledgement selector');
            return { type: 'acknowledged', resources: [], generation };
        }
        if (eventType !== WEBSOCKET_EVENT_TYPES.INVALID_RESOURCE_INTEREST) throw new Error('Invalid resource interest protocol event type');
        const reason = protocolPayload['reason'];
        if (!isString(reason) || !RESOURCE_INTEREST_REJECTION_REASONS.has(reason)) throw new Error('Invalid resource interest protocol rejection reason');
        const resourcesValue = protocolPayload['resources'];
        const resources = resourcesValue === undefined && reason === 'malformed' ? demandedResources : this.#readResources(resourcesValue);
        if (generation < this.#generation) return { type: 'ignored', resources: [] };
        if (generation > this.#generation) throw new Error('Invalid resource interest protocol future generation');
        if (resources.some((resource) => !demandedResources.includes(resource))) throw new Error('Invalid resource interest protocol rejection resources');
        return { type: 'rejected', resources, generation };
    }

    clear(): void {
        if (this.#resourceByToken.size > 0) this.#generation += 1;
        this.#resourceByToken.clear();
        this.#chatPresentationConversationId = null;
    }

    #readErrorDetails(payload: JsonObject): JsonObject {
        const error = payload['error'];
        if (!isJsonObject(error) || !isJsonObject(error['details'])) throw new Error('Invalid resource interest protocol error details');
        return error['details'];
    }

    #readResources(value: JsonValue | undefined): string[] {
        if (!Array.isArray(value) || value.some((resource) => !isString(resource) || !resource.trim())) throw new Error('Invalid resource interest protocol resources');
        const resources = [...new Set(value.map((resource) => resource.trim()))].sort((left, right) => left.localeCompare(right, 'en'));
        if (resources.length !== value.length) throw new Error('Invalid resource interest protocol duplicate resources');
        return resources;
    }

    #readChatPresentationSelector(value: JsonValue | undefined, resources: string[]): string | null {
        if (!resources.includes(WEBUI_CHAT_PRESENTATION)) {
            if (value !== null) throw new Error('Invalid resource interest protocol inactive selector');
            return null;
        }
        if (!isString(value) || !value.trim() || value.trim() !== value) throw new Error('Invalid resource interest protocol selector');
        return value;
    }

    #resources(): string[] {
        return [...new Set(this.#resourceByToken.values())].sort((left, right) => left.localeCompare(right, 'en'));
    }
}

export { LiveResourceInterestState, isLiveResourceInterest };
export type { LiveResourceInterestServerOutcome };
