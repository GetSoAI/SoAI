/* SoAI - Durable conversation input preview state [frontend/assets/ts/features/chat/conversationinputs/ConversationInputStateStore.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

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
    readonly #unconfirmedHeadConversationIds = new Set<string>();
    readonly #steerFollowsConversationIds = new Set<string>();
    readonly #pendingAdmissionsByConversationId = new Map<string, number>();
    #lastRenderedConversationId: string | null = null;

    reset(): void {
        this.#inputsByConversationId.clear();
        this.#activeInputIdsByConversationId.clear();
        this.#settlementObservationsByConversationId.clear();
        this.#syncVersionByConversationId.clear();
        this.#headInputIdByConversationId.clear();
        this.#unconfirmedHeadConversationIds.clear();
        this.#steerFollowsConversationIds.clear();
        this.#pendingAdmissionsByConversationId.clear();
        this.#lastRenderedConversationId = null;
    }

    getQueuedInputs(conversationId: string): ConversationInput[] {
        const stored = this.#inputsByConversationId.get(conversationId);
        const headInputId = this.#unconfirmedHeadConversationIds.has(conversationId) ? undefined : this.#headInputIdByConversationId.get(conversationId);
        return stored ? stored.filter((input) => input.inputId !== headInputId && !input.isRegeneration) : [];
    }

    getSteeringTargetInputId(conversationId: string): string | null {
        return this.#inputsByConversationId.get(normalizeConversationId(conversationId))?.find((input) => (input.inputType === 'prompt' || input.inputType === 'steer') && (input.state === 'materializing' || input.state === 'running'))?.inputId ?? null;
    }

    hasDispatchableHead(conversationId: string): boolean {
        const normalizedConversationId = normalizeConversationId(conversationId);
        return this.#headInputIdByConversationId.has(normalizedConversationId) || this.#steerFollowsConversationIds.has(normalizedConversationId);
    }

    hasActiveInputs(conversationId: string): boolean {
        return (this.#activeInputIdsByConversationId.get(normalizeConversationId(conversationId))?.size ?? 0) > 0;
    }

    upsertAdmittedInput(conversationId: string, input: ConversationInput, isDispatchableHead: boolean): boolean {
        const identity = this.#normalizeIdentity(conversationId, input.inputId);
        if (!identity || this.#settlementObservationsByConversationId.get(identity.conversationId)?.has(identity.inputId)) {
            return false;
        }
        const stored = this.#inputsByConversationId.get(identity.conversationId) ?? [];
        if (!stored.some((entry) => entry.inputId === identity.inputId)) {
            this.#invalidateSync(identity.conversationId);
            const activeInputIds = this.#activeInputIdsByConversationId.get(identity.conversationId) ?? new Set<string>();
            activeInputIds.add(identity.inputId);
            this.#activeInputIdsByConversationId.set(identity.conversationId, activeInputIds);
            this.#inputsByConversationId.set(identity.conversationId, [...stored, input]);
            if (isDispatchableHead && !input.isHeld && !this.#headInputIdByConversationId.has(identity.conversationId)) {
                this.#headInputIdByConversationId.set(identity.conversationId, identity.inputId);
                this.#unconfirmedHeadConversationIds.delete(identity.conversationId);
            }
        }
        return this.#headInputIdByConversationId.get(identity.conversationId) === identity.inputId;
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

    recordTerminalInput(conversationId: string, inputId: string, options: { cancelled?: boolean; steerFollows?: boolean } = {}): void {
        const identity = this.#normalizeIdentity(conversationId, inputId);
        if (!identity) {
            return;
        }
        const previousHeadInputId = this.#headInputIdByConversationId.get(identity.conversationId);
        this.#invalidateSync(identity.conversationId);
        const observations = this.#settlementObservationsByConversationId.get(identity.conversationId);
        const existing = observations?.get(identity.inputId);
        const observation = this.#observeSettlement(identity.conversationId, identity.inputId, 'event');
        if (!existing) observation.pending = true;
        this.#removeActiveInput(identity.conversationId, identity.inputId);
        this.#assignDispatchableHead(identity.conversationId);
        const nextHeadInputId = this.#headInputIdByConversationId.get(identity.conversationId);
        if (options.cancelled === true && previousHeadInputId === identity.inputId && nextHeadInputId !== undefined) {
            this.#unconfirmedHeadConversationIds.add(identity.conversationId);
        }
        if (options.steerFollows === true) {
            this.#steerFollowsConversationIds.add(identity.conversationId);
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
            this.#assignDispatchableHead(conversationId);
        }
    }

    #assignDispatchableHead(conversationId: string): void {
        const nextHead = this.#inputsByConversationId.get(conversationId)?.find((input) => !input.isHeld);
        if (nextHead) {
            this.#headInputIdByConversationId.set(conversationId, nextHead.inputId);
        } else {
            this.#headInputIdByConversationId.delete(conversationId);
            this.#unconfirmedHeadConversationIds.delete(conversationId);
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
        this.#unconfirmedHeadConversationIds.delete(conversationId);
        this.#steerFollowsConversationIds.delete(conversationId);
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
        this.#inputsByConversationId.set(conversationId, activeInputs);
        this.#assignDispatchableHead(conversationId);
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
