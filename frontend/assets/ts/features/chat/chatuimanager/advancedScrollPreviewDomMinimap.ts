/* SoAI - Advanced scroll preview minimap synchronization [frontend/assets/ts/features/chat/chatuimanager/advancedScrollPreviewDomMinimap.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';
import { syncStyleProperty } from '@core/dom/patching.ts';
import { cloneMinimapMessage, type MinimapCloneLayout, mutationTouchesMessageList, patchMinimapCloneInPlace, resolveMinimapCloneStateSignature } from '@features/chat/chatuimanager/advancedScrollPreviewDomClones.ts';
import type { MainTimelineCoordinator } from '@features/chat/mainTimelineCoordinator.ts';

export type AdvancedScrollPreviewDomMinimapRuntime = {
    markDirtyFromMutations: (mutations: MutationRecord[]) => boolean;
    markDirtyFromResize: (entries: readonly ResizeObserverEntry[]) => void;
    measure: () => AdvancedScrollPreviewDomMinimapMeasurement | null;
    apply: (measurement: AdvancedScrollPreviewDomMinimapMeasurement) => boolean;
    hasVisibleContent: () => boolean;
    dispose: () => void;
};

type MinimapMeasuredEntry = {
    messageId: string;
    source: HTMLElement;
    layout: MinimapCloneLayout;
};

type AdvancedScrollPreviewDomMinimapMeasurement = {
    heightPx: number;
    widthPx: number;
    entries: readonly MinimapMeasuredEntry[];
    orderedIds: readonly string[] | null;
};

const isMessageId = (value: string | null): value is string => typeof value === 'string' && value.trim().length > 0;
const MIN_PROJECTED_MESSAGE_HEIGHT_PX = 8;

const collectSourceEntries = (messagesRoot: HTMLElement): HTMLElement[] => {
    const entries: HTMLElement[] = [];
    for (const child of Array.from(messagesRoot.children)) {
        if (child instanceof HTMLElement && (child.classList.contains('chat-message') || child.classList.contains('chat-comparison-turn'))) {
            entries.push(child);
        }
    }
    return entries;
};

export const createAdvancedScrollPreviewDomMinimapRuntime = (input: { coordinator: MainTimelineCoordinator; doc: Document; messagesArea: HTMLElement; messagesRoot: HTMLElement; overlay: HTMLElement; host: HTMLElement }): AdvancedScrollPreviewDomMinimapRuntime => {
    const { coordinator, doc, messagesArea, messagesRoot, overlay, host } = input;

    const observedSourceById = new Map<string, HTMLElement>();
    let observedMessageIdBySource = new WeakMap<HTMLElement, string>();
    const resizeDisposerById = new Map<string, () => void>();
    let needsFullReconcile = true;
    let earliestDirtyIndex: number | null = null;
    let isDisposed = false;
    let orderedSources: HTMLElement[] = [];
    let sourceIndexByElement = new WeakMap<HTMLElement, number>();
    let cloneOrderDirty = true;
    let lastProjection: { hasUsableWidth: boolean; heightPx: number; scrollHeight: number } | null = null;
    const sourceGeometryById = new Map<string, { topPx: number; heightPx: number }>();

    const cloneById = new Map<string, HTMLElement>();
    const cloneStateSignatureById = new Map<string, string>();

    const root = doc.createElement('div');
    root.className = 'chat-advanced-scroll-minimap-root';
    const inner = doc.createElement('div');
    inner.className = 'chat-advanced-scroll-minimap-inner';
    const minimapArea = doc.createElement('div');
    minimapArea.className = 'chat-advanced-scroll-minimap-area';
    const minimapMessages = doc.createElement('div');
    minimapMessages.className = 'chat-advanced-scroll-minimap-messages';
    minimapArea.appendChild(minimapMessages);
    inner.appendChild(minimapArea);
    root.appendChild(inner);

    host.replaceChildren(root);

    const observeSourceMessage = (messageId: string, source: HTMLElement): void => {
        const existing = observedSourceById.get(messageId) ?? null;
        if (existing === source) {
            return;
        }
        if (existing) {
            resizeDisposerById.get(messageId)?.();
        }
        observedSourceById.set(messageId, source);
        observedMessageIdBySource.set(source, messageId);
        resizeDisposerById.set(messageId, coordinator.observeResize(source));
    };

    const resolveCloneLayout = (geometry: { topPx: number; heightPx: number }, overlayWidth: number, overlayHeight: number, scrollHeight: number): MinimapCloneLayout => {
        if (overlayWidth <= 0 || overlayHeight <= 0 || scrollHeight <= 0) {
            return { topPx: 0, heightPx: MIN_PROJECTED_MESSAGE_HEIGHT_PX };
        }
        const scaleY = clampNumber(overlayHeight / scrollHeight, 0.001, 1);
        return {
            topPx: geometry.topPx * scaleY,
            heightPx: Math.max(MIN_PROJECTED_MESSAGE_HEIGHT_PX, geometry.heightPx * scaleY)
        };
    };

    const reconcileSources = (): void => {
        const reconciledSources = collectSourceEntries(messagesRoot);
        cloneOrderDirty = cloneOrderDirty || reconciledSources.length !== orderedSources.length || reconciledSources.some((source, index) => source !== orderedSources[index]);
        orderedSources = reconciledSources;
        sourceIndexByElement = new WeakMap();
        for (let index = 0; index < orderedSources.length; index += 1) {
            const source = orderedSources[index];
            if (source) sourceIndexByElement.set(source, index);
        }
        earliestDirtyIndex = 0;
        needsFullReconcile = false;
    };

    const refreshDirtyGeometry = (): number | null => {
        const dirtyIndex = earliestDirtyIndex;
        if (dirtyIndex === null) return null;
        for (let index = dirtyIndex; index < orderedSources.length; index += 1) {
            const source = orderedSources[index];
            if (!source) continue;
            const rawMessageId = source.getAttribute('data-id');
            if (!isMessageId(rawMessageId)) continue;
            const messageId = rawMessageId.trim();
            observeSourceMessage(messageId, source);
            sourceGeometryById.set(messageId, { topPx: source.offsetTop, heightPx: coordinator.getCachedElementHeight(source) ?? source.offsetHeight });
        }
        earliestDirtyIndex = null;
        return dirtyIndex;
    };

    const measure = (): AdvancedScrollPreviewDomMinimapMeasurement | null => {
        if (isDisposed || !host.isConnected || !messagesArea.isConnected || !messagesRoot.isConnected || !overlay.isConnected) {
            return null;
        }
        const widthPx = Math.max(0, overlay.clientWidth);
        const heightPx = Math.max(0, overlay.clientHeight);
        const scrollHeight = messagesArea.scrollHeight;
        const hasUsableWidth = widthPx > 0;
        if (needsFullReconcile) reconcileSources();
        for (let index = 0; index < orderedSources.length; index += 1) {
            const source = orderedSources[index];
            if (!source) continue;
            const rawMessageId = source.getAttribute('data-id');
            const messageId = isMessageId(rawMessageId) ? rawMessageId.trim() : null;
            const observedMessageId = observedMessageIdBySource.get(source) ?? null;
            if (observedMessageId !== null && observedMessageId !== messageId) {
                cloneOrderDirty = true;
                earliestDirtyIndex = earliestDirtyIndex === null ? index : Math.min(earliestDirtyIndex, index);
            }
        }
        const projectionChanged = lastProjection === null || lastProjection.heightPx !== heightPx || lastProjection.hasUsableWidth !== hasUsableWidth || lastProjection.scrollHeight !== scrollHeight;
        if (cloneOrderDirty) earliestDirtyIndex = 0;
        if (projectionChanged) earliestDirtyIndex = 0;
        const dirtyIndex = refreshDirtyGeometry();
        lastProjection = { hasUsableWidth, heightPx, scrollHeight };
        const entries: MinimapMeasuredEntry[] = [];
        const orderedIds: string[] | null = cloneOrderDirty ? [] : null;
        for (let index = 0; index < orderedSources.length; index += 1) {
            const source = orderedSources[index];
            if (!source) continue;
            const rawMessageId = source.getAttribute('data-id');
            if (!isMessageId(rawMessageId)) {
                continue;
            }
            const messageId = rawMessageId.trim();
            orderedIds?.push(messageId);
            if (dirtyIndex === null || index < dirtyIndex) continue;
            const geometry = sourceGeometryById.get(messageId);
            if (!geometry) {
                throw new Error('Advanced scroll preview source geometry is incomplete after reconciliation.');
            }
            entries.push({
                messageId,
                source,
                layout: resolveCloneLayout(geometry, widthPx, heightPx, scrollHeight)
            });
        }
        return { heightPx, widthPx, entries, orderedIds };
    };

    const apply = (measurement: AdvancedScrollPreviewDomMinimapMeasurement): boolean => {
        if (isDisposed) {
            return false;
        }
        syncStyleProperty(inner, 'width', `${measurement.widthPx}px`);
        syncStyleProperty(inner, 'height', `${measurement.heightPx}px`);
        let removedThisSync = false;
        if (measurement.orderedIds !== null) {
            const present = new Set(measurement.orderedIds);
            for (const [existingId, existingClone] of cloneById) {
                if (present.has(existingId)) continue;
                existingClone.remove();
                cloneById.delete(existingId);
                cloneStateSignatureById.delete(existingId);
                resizeDisposerById.get(existingId)?.();
                resizeDisposerById.delete(existingId);
                observedSourceById.delete(existingId);
                sourceGeometryById.delete(existingId);
                removedThisSync = true;
            }
        }

        const MAX_NEW_CLONES_PER_FRAME = 256;
        let createdThisSync = 0;
        let hasPending = false;

        for (const entry of measurement.entries) {
            if (cloneById.has(entry.messageId)) continue;
            if (createdThisSync >= MAX_NEW_CLONES_PER_FRAME) {
                hasPending = true;
                continue;
            }
            const created = cloneMinimapMessage(entry.source, entry.layout);
            cloneById.set(entry.messageId, created);
            cloneStateSignatureById.set(entry.messageId, resolveMinimapCloneStateSignature(entry.source, entry.layout));
            createdThisSync += 1;
        }

        const shouldReorder = cloneOrderDirty || removedThisSync || createdThisSync > 0;
        for (const entry of measurement.entries) {
            const clone = cloneById.get(entry.messageId);
            if (!clone) continue;
            const stateSignature = resolveMinimapCloneStateSignature(entry.source, entry.layout);
            if (cloneStateSignatureById.get(entry.messageId) !== stateSignature) {
                patchMinimapCloneInPlace(clone, entry.source, entry.layout);
                cloneStateSignatureById.set(entry.messageId, stateSignature);
            }
        }
        if (shouldReorder && measurement.orderedIds !== null) {
            let currentClone = minimapMessages.firstElementChild;
            for (const messageId of measurement.orderedIds) {
                const clone = cloneById.get(messageId);
                if (!clone) continue;
                if (clone !== currentClone) {
                    minimapMessages.insertBefore(clone, currentClone);
                } else {
                    currentClone = currentClone.nextElementSibling;
                }
            }
        }
        cloneOrderDirty = hasPending;

        return hasPending;
    };

    const hasVisibleContent = (): boolean => {
        if (isDisposed) {
            return false;
        }
        const clones = minimapMessages.children;
        if (clones.length === 0) {
            return false;
        }
        for (let index = 0; index < clones.length; index += 1) {
            const clone = clones[index];
            if (!(clone instanceof HTMLElement) || clone.hidden) {
                continue;
            }
            return true;
        }
        return false;
    };

    const markDirtyFromMutations = (mutations: MutationRecord[]): boolean => {
        if (isDisposed || mutations.length === 0) {
            return false;
        }
        let changed = false;
        for (const mutation of mutations) {
            if (mutationTouchesMessageList(mutation, messagesRoot)) {
                needsFullReconcile = true;
                changed = true;
            }
        }
        return changed;
    };

    const markDirtyFromResize = (entries: readonly ResizeObserverEntry[]): void => {
        if (isDisposed) return;
        let dirtyIndex: number | null = null;
        let rootResized = false;
        for (const entry of entries) {
            if (entry.target === messagesRoot) {
                rootResized = true;
                continue;
            }
            const index = entry.target instanceof HTMLElement ? (sourceIndexByElement.get(entry.target) ?? -1) : -1;
            if (index >= 0) dirtyIndex = dirtyIndex === null ? index : Math.min(dirtyIndex, index);
        }
        if (dirtyIndex !== null) earliestDirtyIndex = earliestDirtyIndex === null ? dirtyIndex : Math.min(earliestDirtyIndex, dirtyIndex);
        else if (rootResized) needsFullReconcile = true;
    };

    const dispose = (): void => {
        if (isDisposed) {
            return;
        }
        isDisposed = true;
        host.replaceChildren();
        cloneById.clear();
        cloneStateSignatureById.clear();
        for (const resizeDisposer of resizeDisposerById.values()) {
            resizeDisposer();
        }
        resizeDisposerById.clear();
        observedSourceById.clear();
        sourceGeometryById.clear();
        orderedSources = [];
        sourceIndexByElement = new WeakMap();
        observedMessageIdBySource = new WeakMap();
    };

    return { markDirtyFromMutations, markDirtyFromResize, measure, apply, hasVisibleContent, dispose };
};

export type { AdvancedScrollPreviewDomMinimapMeasurement };
