/* SoAI - Incremental find text work and shared timeline frame ownership [frontend/assets/ts/pages/chat/controllers/conversationfind/ConversationFindTimelineController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { LatestRequestController } from '@core/concurrency/latestRequest.ts';
import { runWithAbortSignalScope } from '@core/errors/abort.ts';
import { requireRootHTMLElement } from '@core/dom/typedElementResolver.ts';
import { INTERFACE_SCALE_CHANGED_EVENT } from '@core/layout/interfaceScale.ts';
import { createLiteralSearchQuery } from '@core/search/literalOccurrences.ts';
import type { ResourceTracker } from '@core/resourcetracker/service.ts';
import { acquireMainTimelineCoordinator, MountedConversationFindIndex, type Conversation, type MainTimelineCoordinator, type MessageSearchTextProjection } from '@features/chat/public.ts';
import { ConversationFindHighlightsController } from '@pages/chat/controllers/conversationfind/ConversationFindHighlightsController.ts';
import type { ConversationFindSearchController } from '@pages/chat/controllers/conversationfind/ConversationFindSearchController.ts';

interface ConversationFindTimelineControllerDependencies {
    root: HTMLElement;
    search: ConversationFindSearchController;
    resources: ResourceTracker;
    current(): Conversation | null;
    createProjection(): MessageSearchTextProjection;
    isPendingDeletion(conversation: Conversation, messageId: string): boolean;
    runTask(operationId: string, task: () => Promise<void>): void;
}

class ConversationFindTimelineController {
    readonly mounted: MountedConversationFindIndex;
    readonly highlights: ConversationFindHighlightsController;
    readonly messages: HTMLElement;
    readonly #dependencies: ConversationFindTimelineControllerDependencies;
    readonly #coordinator: MainTimelineCoordinator;
    readonly #indexRequests = new LatestRequestController();
    readonly #paintRequests = new LatestRequestController();
    readonly #exits: (() => void)[] = [];
    #dirtyTimer: number | null = null;
    #dirty = new Set<string>();
    #fullRefresh = true;
    #disposed = false;

    constructor(dependencies: ConversationFindTimelineControllerDependencies) {
        this.#dependencies = dependencies;
        const { root, resources } = dependencies;
        const area = requireRootHTMLElement(root, '.chat-messages-area', 'Conversation find messages area');
        this.messages = requireRootHTMLElement(root, '.chat-messages', 'Conversation find messages');
        const layer = requireRootHTMLElement(root, '.conversation-find-pop-layer', 'Conversation find overlay');
        const minimap = requireRootHTMLElement(root, '.conversation-find-marks', 'Conversation find minimap');
        this.#coordinator = acquireMainTimelineCoordinator(area, this.messages);
        this.mounted = new MountedConversationFindIndex({ root: this.messages, createProjection: dependencies.createProjection, isPendingDeletion: dependencies.isPendingDeletion });
        this.highlights = new ConversationFindHighlightsController({ area, layer, minimap, mounted: this.mounted, coordinator: this.#coordinator });
        this.#exits.push(
            this.#coordinator.subscribeMutations((records) => {
                if (!dependencies.search.snapshot.open) return;
                for (const record of records) {
                    const element = record.target instanceof Element ? record.target : record.target.parentElement;
                    const row = element?.closest('.chat-message[data-id]');
                    const id = row?.getAttribute('data-id');
                    if (id) this.#dirty.add(id);
                    else if (record.type === 'childList') this.#fullRefresh = true;
                }
                this.scheduleRefresh();
            })
        );
        this.#exits.push(this.#coordinator.subscribeResize(() => this.#geometry(true)));
        this.#exits.push(this.#coordinator.observeResize(area));
        this.#exits.push(resources.addEventListener(area, 'scroll', () => this.#geometry(false), { passive: true }));
        const view = root.ownerDocument.defaultView;
        if (view) this.#exits.push(resources.addEventListener(view, INTERFACE_SCALE_CHANGED_EVENT, () => this.#geometry(true)));
    }

    #geometry(minimap: boolean): void {
        const generation = this.#dependencies.search.generation;
        this.highlights.scheduleGeometry(() => !this.#disposed && this.#dependencies.search.isCurrent(generation), minimap);
    }

    clear(): void {
        this.#indexRequests.invalidate();
        this.#paintRequests.invalidate();
        if (this.#dirtyTimer !== null) this.#dependencies.resources.clearTimer(this.#dirtyTimer);
        this.#dirtyTimer = null;
        this.#dirty.clear();
        this.#fullRefresh = true;
        this.highlights.stopMovement();
        this.highlights.clear();
        this.mounted.clear();
    }

    readonly scheduleRefresh = (): void => {
        const { search, resources } = this.#dependencies;
        if (this.#disposed || !search.snapshot.open || !search.snapshot.query || this.#dirtyTimer !== null) return;
        search.observeAuthority();
        const generation = search.generation;
        const timerId = resources.setTimeout(() => {
            if (this.#dirtyTimer !== timerId) return;
            this.#dirtyTimer = null;
            if (search.isCurrent(generation)) this.#dependencies.runTask('chat:find:live', () => this.refresh());
        }, 0);
        this.#dirtyTimer = timerId;
    };

    async refresh(signal?: AbortSignal, messageId?: string): Promise<void> {
        const { search } = this.#dependencies;
        const conversation = this.#dependencies.current();
        const generation = search.generation;
        if (this.#disposed || !conversation || !search.snapshot.query || !search.isCurrent(generation) || search.snapshot.status === 'too-long') return;
        const dirty = this.#fullRefresh ? null : new Set(this.#dirty);
        if (messageId) dirty?.add(messageId);
        this.#dirty.clear();
        this.#fullRefresh = false;
        await this.#indexRequests.runLatest(async (request) => {
            await runWithAbortSignalScope([signal, request.signal], async (combined) => {
                const isCurrent = (): boolean => request.isCurrent() && !this.#disposed && search.isCurrent(generation);
                const result = await this.mounted.refresh(conversation, createLiteralSearchQuery(search.snapshot.query), dirty, combined, isCurrent);
                if (result && isCurrent()) search.applyLiveEntries(generation, result.entries, result.mountedIds);
            });
        });
    }

    paint(): void {
        const { search } = this.#dependencies;
        const generation = search.generation;
        this.#dependencies.runTask('chat:find:paint', async () => {
            if (this.#disposed || !search.isCurrent(generation)) return;
            await this.#paintRequests.runLatest(async (request) => {
                await this.highlights.paint(search.snapshot.index, search.snapshot.target, request.signal, () => request.isCurrent() && !this.#disposed && search.isCurrent(generation));
            });
            if (!this.#disposed && search.isCurrent(generation)) this.#geometry(true);
        });
    }

    dispose(): void {
        if (this.#disposed) return;
        this.#disposed = true;
        this.clear();
        for (const exit of this.#exits) exit();
        this.#coordinator.release();
    }
}

export { ConversationFindTimelineController };
