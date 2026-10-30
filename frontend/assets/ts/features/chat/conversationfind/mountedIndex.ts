/* SoAI - Mounted message text indexing and fresh occurrence ranges [frontend/assets/ts/features/chat/conversationfind/mountedIndex.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { createSearchTextRange, visitSearchTextBlocks, type SearchTextBlock } from '@core/search/domTextIndex.ts';
import { scanLiteralOccurrences, type LiteralSearchQuery } from '@core/search/literalOccurrences.ts';
import { SearchWorkBudget } from '@core/search/searchWorkBudget.ts';
import { throwIfAborted } from '@core/errors/abort.ts';
import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { createConversationFindEntry } from '@features/chat/message/messageRenderSignature.ts';
import type { ConversationFindEntry, ConversationFindTarget } from '@features/chat/conversationfind/contracts.ts';
import { compareConversationFindEntries, type ConversationFindResultIndex } from '@features/chat/conversationfind/searchResults.ts';
import { resolveConversationFindMessages } from '@features/chat/conversationfind/searchMessages.ts';
import { presentedChatSearchTextTraversalPolicy } from '@features/chat/message/searchTextPolicy.ts';
import type { MessageSearchTextProjection } from '@features/chat/message/searchTextProjection.ts';
import type { Conversation } from '@features/chat/storage/storageModels.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { resolveStableMessageDomId } from '@features/chat/message/messageDomIds.ts';
import { resolveAssistantMessageRevisionNumberFromMessage } from '@features/chat/message/messageSegmentsResolution.ts';

interface MountedFindMessage {
    entry: ConversationFindEntry;
    body: HTMLElement | null;
    blocks: readonly SearchTextBlock[];
    pendingDeletion: boolean;
    sourceMessage: ChatMessage;
    assistantRevision: number;
}

interface MountedConversationFindDependencies {
    root: HTMLElement;
    createProjection(): MessageSearchTextProjection;
    isPendingDeletion(conversation: Conversation, messageId: string): boolean;
}

const isPresentedFindBody = (body: HTMLElement): boolean => {
    if (!body.isConnected || body.closest('[inert], [hidden], .u-hidden, .is-editing')) return false;
    const style = body.ownerDocument.defaultView?.getComputedStyle(body);
    return style !== undefined && style.display !== 'none' && style.visibility !== 'hidden';
};

class MountedConversationFindIndex {
    readonly #dependencies: MountedConversationFindDependencies;
    #messages = new Map<string, MountedFindMessage>();
    #query: LiteralSearchQuery = { foldedText: '' };

    constructor(dependencies: MountedConversationFindDependencies) {
        this.#dependencies = dependencies;
    }

    clear(): void {
        this.#messages.clear();
        this.#query = { foldedText: '' };
    }

    get bodies(): readonly HTMLElement[] {
        return Array.from(this.#messages.values()).flatMap((message) => (message.body === null ? [] : [message.body]));
    }

    body(messageId: string): HTMLElement | null {
        const body = this.#messages.get(messageId)?.body;
        return body && isPresentedFindBody(body) ? body : null;
    }

    async refresh(conversation: Conversation, query: LiteralSearchQuery, dirty: ReadonlySet<string> | null, signal: AbortSignal, isCurrent: () => boolean): Promise<{ entries: readonly ConversationFindEntry[]; mountedIds: ReadonlySet<string> } | null> {
        const budget = new SearchWorkBudget(this.#dependencies.root.ownerDocument.defaultView, signal);
        const queryChanged = query.foldedText !== this.#query.foldedText;
        let project: MessageSearchTextProjection | null = null;
        const next = new Map<string, MountedFindMessage>();
        const rows = new Map(dom.resolveAll('.chat-message[data-id]', this.#dependencies.root).map((row) => [row.getAttribute('data-id'), row]));
        for (const { message, orderMessage } of resolveConversationFindMessages(conversation.messages)) {
            await budget.checkpoint();
            if (!isCurrent()) return null;
            const messageId = resolveStableMessageDomId(message);
            if (messageId === null) throw new Error('Mounted conversation search requires a stable identity');
            const previous = queryChanged ? undefined : this.#messages.get(messageId);
            const row = rows.get(messageId);
            const candidate = row ? dom.resolve('.message-text', row) : null;
            const body = candidate instanceof HTMLElement && isPresentedFindBody(candidate) ? candidate : null;
            const pending = this.#dependencies.isPendingDeletion(conversation, messageId);
            const assistantRevision = resolveAssistantMessageRevisionNumberFromMessage(message);
            if (previous && previous.sourceMessage === message && previous.assistantRevision === assistantRevision && previous.pendingDeletion === pending && previous.body === body && previous.entry.cursor?.id === (typeof message.id === 'number' ? message.id : undefined) && !dirty?.has(messageId) && dirty !== null) {
                next.set(messageId, previous);
                continue;
            }
            const identity = createConversationFindEntry(message, 0, orderMessage);
            const blocks: SearchTextBlock[] = [];
            let count = 0;
            const countBlock = async (block: SearchTextBlock): Promise<boolean> => {
                count += (await scanLiteralOccurrences(block.text, query, budget)).count;
                if (body !== null) blocks.push(block);
                return true;
            };
            if (!pending) {
                if (body !== null) await visitSearchTextBlocks(body, presentedChatSearchTextTraversalPolicy, budget, countBlock);
                else {
                    project ??= this.#dependencies.createProjection();
                    await project(message, budget, countBlock);
                }
            }
            if (!isCurrent()) return null;
            next.set(identity.messageId, { entry: { ...identity, count }, body, blocks, pendingDeletion: pending, sourceMessage: message, assistantRevision });
        }
        throwIfAborted(signal);
        if (!isCurrent()) return null;
        this.#query = query;
        this.#messages = next;
        return { entries: Array.from(next.values(), (message) => message.entry), mountedIds: new Set(next.keys()) };
    }

    async range(target: ConversationFindTarget, signal: AbortSignal): Promise<Range | null> {
        const message = this.#messages.get(target.messageId);
        if (!message?.body || !isPresentedFindBody(message.body)) return null;
        const budget = new SearchWorkBudget(message.body.ownerDocument.defaultView, signal);
        let occurrenceIndex = 0;
        const resolved: { range: Range | null } = { range: null };
        for (const block of message.blocks) {
            const result = await scanLiteralOccurrences(block.text, this.#query, budget, (offset) => {
                if (occurrenceIndex++ !== target.occurrenceIndex) return true;
                resolved.range = createSearchTextRange(block, offset, this.#query.foldedText.length);
                return false;
            });
            if (result.stopped) break;
        }
        return resolved.range !== null && message.body.contains(resolved.range.startContainer) && message.body.contains(resolved.range.endContainer) ? resolved.range : null;
    }

    async initialTarget(index: ConversationFindResultIndex, bandTop: number, signal: AbortSignal): Promise<ConversationFindTarget | null> {
        const budget = new SearchWorkBudget(this.#dependencies.root.ownerDocument.defaultView, signal);
        for (const entry of index.entries) {
            const message = this.#messages.get(entry.messageId);
            if (!message?.body || !isPresentedFindBody(message.body) || measureLayoutBox(message.body).bottom < bandTop) continue;
            let occurrenceIndex = 0;
            const found: { target: ConversationFindTarget | null } = { target: null };
            for (const block of message.blocks) {
                const result = await scanLiteralOccurrences(block.text, this.#query, budget, (offset) => {
                    const target = { messageId: entry.messageId, occurrenceIndex: occurrenceIndex++ };
                    const range = createSearchTextRange(block, offset, this.#query.foldedText.length);
                    if (range && measureLayoutBox(range).bottom >= bandTop) {
                        found.target = target;
                        return false;
                    }
                    return true;
                });
                if (result.stopped) return found.target;
            }
        }
        const reference = Array.from(this.#messages.values())
            .filter((message) => message.body && isPresentedFindBody(message.body) && measureLayoutBox(message.body).bottom >= bandTop)
            .sort((left, right) => compareConversationFindEntries(left.entry, right.entry))[0];
        const later = reference ? index.entries.find((entry) => compareConversationFindEntries(entry, reference.entry) >= 0) : null;
        return later ? { messageId: later.messageId, occurrenceIndex: 0 } : index.targetAt(index.totalOccurrences - 1);
    }

    async paintedRanges(messageIds: readonly string[], limit: number, signal: AbortSignal): Promise<Range[]> {
        const ranges: Range[] = [];
        if (limit <= 0) return ranges;
        const budget = new SearchWorkBudget(this.#dependencies.root.ownerDocument.defaultView, signal);
        for (const messageId of messageIds) {
            const message = this.#messages.get(messageId);
            if (!message?.body || !isPresentedFindBody(message.body)) continue;
            for (const block of message.blocks) {
                let runStart: number | null = null;
                let runEnd = 0;
                const flush = (): void => {
                    if (runStart === null || ranges.length >= limit) return;
                    const range = createSearchTextRange(block, runStart, runEnd - runStart);
                    if (range) ranges.push(range);
                    runStart = null;
                };
                await scanLiteralOccurrences(block.text, this.#query, budget, (offset) => {
                    if (runStart !== null && offset > runEnd) flush();
                    if (ranges.length >= limit) return false;
                    runStart ??= offset;
                    runEnd = offset + this.#query.foldedText.length;
                    return true;
                });
                flush();
                if (ranges.length >= limit) return ranges;
            }
        }
        return ranges;
    }
}

export { MountedConversationFindIndex, isPresentedFindBody };
export type { MountedConversationFindDependencies };
