/* SoAI - Conversation find identities, ordering and ordinal lookup [frontend/assets/ts/features/chat/conversationfind/searchResults.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { comparePersistedMessageCursors } from '@features/chat/message/persistedMessageIdentity.ts';
import type { ConversationFindEntry, ConversationFindOverride, ConversationFindTarget } from '@features/chat/conversationfind/contracts.ts';

const CONVERSATION_FIND_MESSAGE_LIMIT = 5000;

interface ConversationFindReconciliation {
    index: ConversationFindResultIndex;
    overrides: readonly ConversationFindOverride[];
    truncated: boolean;
    needsRefill: boolean;
}

const compareConversationFindEntries = (left: ConversationFindEntry, right: ConversationFindEntry): number => {
    if (left.orderCursor !== null && right.orderCursor !== null) {
        const cursorOrder = comparePersistedMessageCursors(left.orderCursor, right.orderCursor);
        if (cursorOrder !== 0) return cursorOrder;
    } else {
        const timestampOrder = left.orderTimestamp - right.orderTimestamp;
        if (timestampOrder !== 0) return timestampOrder;
        if (left.orderCursor !== null) return -1;
        if (right.orderCursor !== null) return 1;
    }
    const variantOrder = (left.comparison?.modelVariantIndex ?? 0) - (right.comparison?.modelVariantIndex ?? 0);
    return variantOrder === 0 ? left.messageId.localeCompare(right.messageId, 'en') : variantOrder;
};

class ConversationFindResultIndex {
    readonly entries: readonly ConversationFindEntry[];
    readonly totalOccurrences: number;
    readonly #cumulativeCounts: number[] = [];

    constructor(entries: readonly ConversationFindEntry[]) {
        if (entries.length > CONVERSATION_FIND_MESSAGE_LIMIT) throw new Error('Conversation search exceeds its matching-message limit');
        for (const entry of entries) {
            if (!Number.isSafeInteger(entry.count) || entry.count < 0) throw new Error('Conversation search entry must have a non-negative count');
        }
        this.entries = entries.filter((entry) => entry.count > 0).toSorted(compareConversationFindEntries);
        let total = 0;
        for (const entry of this.entries) {
            total += entry.count;
            if (!Number.isSafeInteger(total)) throw new Error('Conversation search occurrence count exceeds integer precision');
            this.#cumulativeCounts.push(total);
        }
        this.totalOccurrences = total;
    }

    targetAt(ordinal: number): ConversationFindTarget | null {
        if (!Number.isSafeInteger(ordinal) || ordinal < 0 || ordinal >= this.totalOccurrences) return null;
        let start = 0;
        let end = this.entries.length;
        while (start < end) {
            const middle = Math.floor((start + end) / 2);
            if ((this.#cumulativeCounts[middle] ?? 0) <= ordinal) start = middle + 1;
            else end = middle;
        }
        const entry = this.entries[start];
        return entry ? { messageId: entry.messageId, occurrenceIndex: ordinal - (this.#cumulativeCounts[start - 1] ?? 0) } : null;
    }

    ordinalOf(target: ConversationFindTarget): number | null {
        const index = this.entries.findIndex((entry) => entry.messageId === target.messageId);
        const entry = this.entries[index];
        if (!entry || !Number.isSafeInteger(target.occurrenceIndex) || target.occurrenceIndex < 0 || target.occurrenceIndex >= entry.count) return null;
        return (this.#cumulativeCounts[index - 1] ?? 0) + target.occurrenceIndex;
    }
}

const mergeConversationFindResults = (snapshotEntries: readonly ConversationFindEntry[], snapshotTruncated: boolean, overrides: readonly ConversationFindOverride[]): ConversationFindReconciliation => {
    if (snapshotEntries.length > CONVERSATION_FIND_MESSAGE_LIMIT) throw new Error('Conversation search snapshot exceeds its matching-message limit');
    const entriesByMessageId = new Map(snapshotEntries.map((entry) => [entry.messageId, entry]));
    const entriesBySemanticId = new Map(snapshotEntries.map((entry) => [entry.semanticId, entry]));
    const retainedOverrides: ConversationFindOverride[] = [];
    for (const override of overrides) {
        const original = entriesByMessageId.get(override.entry.messageId) ?? entriesBySemanticId.get(override.entry.semanticId);
        if (!override.mounted && (original === undefined || (original.sourceRevision !== override.baselineSourceRevision && original.sourceRevision !== override.entry.sourceRevision))) continue;
        if (original !== undefined) {
            entriesByMessageId.delete(original.messageId);
            entriesBySemanticId.delete(original.semanticId);
        }
        const entry = original?.cursor && override.entry.cursor === null ? { ...override.entry, messageId: original.messageId, cursor: original.cursor, orderCursor: original.orderCursor, orderTimestamp: original.orderTimestamp } : override.entry;
        entriesByMessageId.set(entry.messageId, entry);
        entriesBySemanticId.set(entry.semanticId, entry);
        retainedOverrides.push({ ...override, entry });
    }
    const matchingEntries = Array.from(entriesByMessageId.values())
        .filter((entry) => entry.count > 0)
        .sort(compareConversationFindEntries);
    const exceededLimit = matchingEntries.length > CONVERSATION_FIND_MESSAGE_LIMIT;
    const index = new ConversationFindResultIndex(exceededLimit ? matchingEntries.slice(-CONVERSATION_FIND_MESSAGE_LIMIT) : matchingEntries);
    return { index, overrides: retainedOverrides, truncated: snapshotTruncated || exceededLimit, needsRefill: snapshotTruncated && index.entries.length < CONVERSATION_FIND_MESSAGE_LIMIT };
};

const preserveConversationFindTarget = (previousIndex: ConversationFindResultIndex, nextIndex: ConversationFindResultIndex, previousTarget: ConversationFindTarget | null): ConversationFindTarget | null => {
    if (previousTarget === null) return null;
    const previousEntry = previousIndex.entries.find((entry) => entry.messageId === previousTarget.messageId);
    if (!previousEntry) return nextIndex.targetAt(0);
    const sameEntry = nextIndex.entries.find((entry) => entry.messageId === previousEntry.messageId || entry.semanticId === previousEntry.semanticId);
    if (sameEntry && previousTarget.occurrenceIndex < sameEntry.count) return { messageId: sameEntry.messageId, occurrenceIndex: previousTarget.occurrenceIndex };
    const successor = nextIndex.entries.find((entry) => compareConversationFindEntries(entry, previousEntry) > 0);
    if (successor) return { messageId: successor.messageId, occurrenceIndex: 0 };
    const predecessor = nextIndex.entries.findLast((entry) => compareConversationFindEntries(entry, previousEntry) <= 0);
    return predecessor ? { messageId: predecessor.messageId, occurrenceIndex: predecessor.count - 1 } : null;
};

export { CONVERSATION_FIND_MESSAGE_LIMIT, ConversationFindResultIndex, compareConversationFindEntries, preserveConversationFindTarget, mergeConversationFindResults };
export type { ConversationFindReconciliation };
