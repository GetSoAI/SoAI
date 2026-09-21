/* SoAI - Durable conversation input preview state [frontend/assets/ts/features/chat/conversationinputs/ConversationInputStateStore.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getCurrentLocale } from '@core/languageservice/service.ts';
import type { ConversationInput } from '@features/chat/conversationinputs/ConversationInputTypes.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

interface SettlementObservation {
    eventObserved: boolean;
    listObserved: boolean;
    pending: boolean;
    reconciled: boolean;
}

class ConversationInputStateStore {
    readonly #inputsByConversationId = new Map<string, ConversationInput[]>();
    readonly #activeInputIdsByConversationId = new Map<string, Set<string>>();
    readonly #settlementObservationsByConversationId = new Map<string, Map<string, SettlementObservation>>();
    readonly #syncVersionByConversationId = new Map<string, number>();
    readonly #headInputIdByConversationId = new Map<string, string>();
    readonly #pendingAdmissionsByConversationId = new Map<string, number>();
    #lastRenderedConversationId: string | null = null;

    reset(): void {
        this.#inputsByConversationId.clear();
        this.#activeInputIdsByConversationId.clear();
        this.#settlementObservationsByConversationId.clear();
        this.#syncVersionByConversationId.clear();
        this.#headInputIdByConversationId.clear();
        this.#pendingAdmissionsByConversationId.clear();
        this.#lastRenderedConversationId = null;
    }

    getQueuedInputs(conversationId: string): ConversationInput[] {
        const stored = this.#inputsByConversationId.get(conversationId);
        const headInputId = this.#headInputIdByConversationId.get(conversationId);
        return stored ? stored.filter((input) => input.inputId !== headInputId && !input.isRegeneration) : [];
    }

    upsertAdmittedInput(conversationId: string, input: ConversationInput, isDispatchableHead: boolean): void {
        const normalizedConversationId = normalizeConversationId(conversationId);
        const normalizedInputId = input.inputId.trim();
        if (!normalizedConversationId || !normalizedInputId) {
            return;
        }
        if (this.#settlementObservationsByConversationId.get(normalizedConversationId)?.has(normalizedInputId)) {
            return;
        }
        this.#invalidateSync(normalizedConversationId);
        const activeInputIds = this.#activeInputIdsByConversationId.get(normalizedConversationId) ?? new Set<string>();
        activeInputIds.add(normalizedInputId);
        this.#activeInputIdsByConversationId.set(normalizedConversationId, activeInputIds);
        if (isDispatchableHead) {
            this.#headInputIdByConversationId.set(normalizedConversationId, normalizedInputId);
        }
        const stored = this.#inputsByConversationId.get(normalizedConversationId) ?? [];
        const next = stored.filter((entry) => entry.inputId !== normalizedInputId);
        next.push(input);
        next.sort((left, right) => {
            if (left.acceptedAtMs !== right.acceptedAtMs) {
                return left.acceptedAtMs - right.acceptedAtMs;
            }
            return left.inputId.localeCompare(right.inputId, getCurrentLocale());
        });
        this.#inputsByConversationId.set(normalizedConversationId, next);
    }

    beginAdmission(conversationId: string): void {
        const pending = this.#pendingAdmissionsByConversationId.get(conversationId) ?? 0;
        this.#pendingAdmissionsByConversationId.set(conversationId, pending + 1);
    }

    completeAdmission(conversationId: string): void {
        const pending = this.#pendingAdmissionsByConversationId.get(conversationId) ?? 0;
        if (pending > 1) {
            this.#pendingAdmissionsByConversationId.set(conversationId, pending - 1);
            return;
        }
        this.#pendingAdmissionsByConversationId.delete(conversationId);
        const observations = this.#settlementObservationsByConversationId.get(conversationId);
        for (const inputId of observations?.keys() ?? []) {
            this.#removeCompletedObservation(conversationId, inputId);
        }
    }

    recordCancelledInput(conversationId: string, inputId: string): void {
        const identity = this.#normalizeIdentity(conversationId, inputId);
        if (!identity) {
            return;
        }
        this.#invalidateSync(identity.conversationId);
        const observation = this.#observeSettlement(identity.conversationId, identity.inputId, 'event');
        observation.reconciled = true;
        observation.pending = false;
        this.#removeActiveInput(identity.conversationId, identity.inputId);
        this.#removeCompletedObservation(identity.conversationId, identity.inputId);
    }

    recordTerminalInput(conversationId: string, inputId: string): void {
        const identity = this.#normalizeIdentity(conversationId, inputId);
        if (!identity) {
            return;
        }
        this.#invalidateSync(identity.conversationId);
        const observations = this.#settlementObservationsByConversationId.get(identity.conversationId);
        const existing = observations?.get(identity.inputId);
        const observation = this.#observeSettlement(identity.conversationId, identity.inputId, 'event');
        if (!existing) observation.pending = true;
        this.#removeActiveInput(identity.conversationId, identity.inputId);
        const nextHead = this.#inputsByConversationId.get(identity.conversationId)?.[0];
        if (nextHead) {
            this.#headInputIdByConversationId.set(identity.conversationId, nextHead.inputId);
        } else {
            this.#headInputIdByConversationId.delete(identity.conversationId);
        }
        this.#removeCompletedObservation(identity.conversationId, identity.inputId);
    }

    #removeVisibleInput(conversationId: string, inputId: string): void {
        const stored = this.#inputsByConversationId.get(conversationId);
        const normalizedInputId = inputId.trim();
        if (!stored || !normalizedInputId) {
            return;
        }
        const next = stored.filter((entry) => entry.inputId !== normalizedInputId);
        if (next.length > 0) {
            this.#inputsByConversationId.set(conversationId, next);
            return;
        }
        this.#inputsByConversationId.delete(conversationId);
    }

    #removeActiveInput(conversationId: string, inputId: string): void {
        const activeInputIds = this.#activeInputIdsByConversationId.get(conversationId);
        activeInputIds?.delete(inputId);
        if (activeInputIds?.size === 0) {
            this.#activeInputIdsByConversationId.delete(conversationId);
        }
        this.#removeVisibleInput(conversationId, inputId);
        if (this.#headInputIdByConversationId.get(conversationId) === inputId) {
            const nextHead = this.#inputsByConversationId.get(conversationId)?.[0];
            if (nextHead) {
                this.#headInputIdByConversationId.set(conversationId, nextHead.inputId);
            } else {
                this.#headInputIdByConversationId.delete(conversationId);
            }
        }
    }

    recordRenderedConversation(conversationId: string | null): string | null {
        const normalizedConversationId = normalizeConversationId(conversationId);
        if (!normalizedConversationId) {
            this.#lastRenderedConversationId = null;
            return null;
        }
        if (normalizedConversationId === this.#lastRenderedConversationId) {
            return null;
        }
        this.#lastRenderedConversationId = normalizedConversationId;
        return normalizedConversationId;
    }

    beginSync(conversationId: string): number {
        const version = (this.#syncVersionByConversationId.get(conversationId) ?? 0) + 1;
        this.#syncVersionByConversationId.set(conversationId, version);
        return version;
    }

    isSyncCurrent(conversationId: string, version: number): boolean {
        return this.#syncVersionByConversationId.get(conversationId) === version;
    }

    applySyncResult(conversationId: string, inputs: ConversationInput[]): void {
        const incomingActiveInputIds = new Set(inputs.map((input) => input.inputId.trim()).filter(Boolean));
        const previousActiveInputIds = this.#activeInputIdsByConversationId.get(conversationId);
        if (previousActiveInputIds) {
            for (const inputId of previousActiveInputIds) {
                if (!incomingActiveInputIds.has(inputId)) {
                    this.#observeListSettlement(conversationId, inputId);
                }
            }
        }
        const observations = this.#settlementObservationsByConversationId.get(conversationId);
        if (observations) {
            for (const [inputId] of observations) {
                if (!incomingActiveInputIds.has(inputId)) {
                    this.#observeSettlement(conversationId, inputId, 'list');
                    this.#removeCompletedObservation(conversationId, inputId);
                }
            }
        }
        const activeInputs = observations ? inputs.filter((input) => !observations.has(input.inputId.trim())) : inputs;
        const activeInputIds = new Set(activeInputs.map((input) => input.inputId.trim()).filter(Boolean));
        if (activeInputIds.size > 0) {
            this.#activeInputIdsByConversationId.set(conversationId, activeInputIds);
        } else {
            this.#activeInputIdsByConversationId.delete(conversationId);
        }
        if (activeInputs.length === 0) {
            this.#inputsByConversationId.delete(conversationId);
            this.#headInputIdByConversationId.delete(conversationId);
            return;
        }
        const headInput = activeInputs[0];
        if (!headInput) {
            throw new Error('Active conversation inputs require an execution head.');
        }
        this.#inputsByConversationId.set(conversationId, activeInputs);
        this.#headInputIdByConversationId.set(conversationId, headInput.inputId);
    }

    takePendingSettlements(conversationId: string): string[] {
        const inputIds: string[] = [];
        const observations = this.#settlementObservationsByConversationId.get(conversationId);
        for (const [inputId, observation] of observations ?? []) {
            if (observation.pending) {
                observation.pending = false;
                inputIds.push(inputId);
            }
        }
        return inputIds;
    }

    restorePendingSettlements(conversationId: string, inputIds: readonly string[]): void {
        const observations = this.#settlementObservationsByConversationId.get(conversationId);
        for (const inputId of inputIds) {
            const observation = observations?.get(inputId);
            if (observation && !observation.reconciled) {
                observation.pending = true;
            }
        }
    }

    completeSettlements(conversationId: string, inputIds: readonly string[]): void {
        const observations = this.#settlementObservationsByConversationId.get(conversationId);
        for (const inputId of inputIds) {
            const observation = observations?.get(inputId);
            if (observation) {
                observation.reconciled = true;
                this.#removeCompletedObservation(conversationId, inputId);
            }
        }
    }

    #normalizeIdentity(conversationId: string, inputId: string): { conversationId: string; inputId: string } | null {
        const normalizedConversationId = normalizeConversationId(conversationId);
        const normalizedInputId = inputId.trim();
        return normalizedConversationId && normalizedInputId ? { conversationId: normalizedConversationId, inputId: normalizedInputId } : null;
    }

    #invalidateSync(conversationId: string): void {
        this.#syncVersionByConversationId.set(conversationId, (this.#syncVersionByConversationId.get(conversationId) ?? 0) + 1);
    }

    #observeListSettlement(conversationId: string, inputId: string): void {
        const observations = this.#settlementObservationsByConversationId.get(conversationId);
        const alreadyObserved = observations?.has(inputId) === true;
        const observation = this.#observeSettlement(conversationId, inputId, 'list');
        if (!alreadyObserved) observation.pending = true;
    }

    #observeSettlement(conversationId: string, inputId: string, source: 'event' | 'list'): SettlementObservation {
        const observations = this.#settlementObservationsByConversationId.get(conversationId) ?? new Map<string, SettlementObservation>();
        const observation = observations.get(inputId) ?? { eventObserved: false, listObserved: false, pending: false, reconciled: false };
        if (source === 'event') {
            observation.eventObserved = true;
        } else {
            observation.listObserved = true;
        }
        observations.set(inputId, observation);
        this.#settlementObservationsByConversationId.set(conversationId, observations);
        return observation;
    }

    #removeCompletedObservation(conversationId: string, inputId: string): void {
        if ((this.#pendingAdmissionsByConversationId.get(conversationId) ?? 0) > 0) {
            return;
        }
        const observations = this.#settlementObservationsByConversationId.get(conversationId);
        const observation = observations?.get(inputId);
        if (!observation?.eventObserved || !observation.listObserved || !observation.reconciled) {
            return;
        }
        observations?.delete(inputId);
        if (observations?.size === 0) {
            this.#settlementObservationsByConversationId.delete(conversationId);
        }
    }
}

export { ConversationInputStateStore };
