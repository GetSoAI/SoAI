/* SoAI - Chat feature stream scrollable state [frontend/assets/ts/features/chat/stream/streamScrollableState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { isString } from '@core/typeGuards.ts';

type KeyedScrollState = {
    scrollTop: number;
    scrollLeft: number;
    stickToBottom: boolean;
    stickToRight: boolean;
};

const SCROLL_EDGE_TOLERANCE_PX = 2;

type ScrollableType = 'pre' | 'details';

const resolveCustomScrollKey = (node: HTMLElement): string | null => {
    const raw = node.getAttribute('data-scroll-key');
    if (!isString(raw) || !raw.trim()) {
        return null;
    }
    return raw.trim();
};

const resolveScrollableGroupKey = (node: HTMLElement): string => {
    const activity = node.closest('.inline-activity[data-call-id]');
    const callIdValue = activity?.getAttribute('data-call-id') ?? '';
    const callId = toTrimmedString(callIdValue);
    return callId ? `call:${callId}` : 'message';
};

const resolveScrollableType = (node: HTMLElement): ScrollableType | null => {
    if (node.tagName.toLowerCase() === 'pre') {
        return 'pre';
    }
    if (node.classList.contains('inline-activity-details')) {
        return 'details';
    }
    return null;
};

const shouldCaptureScrollableState = (node: HTMLElement, scrollableType: ScrollableType): boolean => {
    if (scrollableType === 'details') {
        return true;
    }
    return node.scrollHeight > node.clientHeight || node.scrollWidth > node.clientWidth;
};

const resolveScrollableStateKey = (node: HTMLElement, scrollableType: ScrollableType, orderByGroupAndType: Map<string, number>): string => {
    const customKey = resolveCustomScrollKey(node);
    if (customKey) {
        return `custom:${customKey}`;
    }
    const groupKey = resolveScrollableGroupKey(node);
    const orderKey = `${groupKey}:${scrollableType}`;
    const ordinal = (orderByGroupAndType.get(orderKey) ?? 0) + 1;
    orderByGroupAndType.set(orderKey, ordinal);
    return `${groupKey}:${scrollableType}:${String(ordinal)}`;
};

const collectScrollableNodes = (container: Element): HTMLElement[] => {
    const nodes: HTMLElement[] = [];
    const stack: Element[] = [container];
    while (stack.length > 0) {
        const current = stack.pop();
        if (!(current instanceof HTMLElement)) {
            continue;
        }
        const scrollableType = resolveScrollableType(current);
        if (scrollableType !== null) {
            nodes.push(current);
        }
        const children = current.children;
        for (let index = children.length - 1; index >= 0; index -= 1) {
            const child = children[index];
            if (child instanceof Element) {
                stack.push(child);
            }
        }
    }
    return nodes;
};

const resolveScrollableStateKeyForTarget = (container: Element, target: HTMLElement): string | null => {
    const orderByGroupAndType = new Map<string, number>();
    for (const node of collectScrollableNodes(container)) {
        const scrollableType = resolveScrollableType(node);
        if (!scrollableType) {
            continue;
        }
        const key = resolveScrollableStateKey(node, scrollableType, orderByGroupAndType);
        if (node === target) {
            return key;
        }
    }
    return null;
};

const scrollNodeToBottom = (node: HTMLElement): void => {
    node.scrollTop = node.scrollHeight;
};

export const readKeyedScrollableState = (container: Element): Map<string, KeyedScrollState> | null => {
    const nodes = collectScrollableNodes(container);
    if (nodes.length === 0) {
        return null;
    }
    const orderByGroupAndType = new Map<string, number>();
    const state = new Map<string, KeyedScrollState>();
    for (const node of nodes) {
        const scrollableType = resolveScrollableType(node);
        if (!scrollableType) {
            continue;
        }
        if (!shouldCaptureScrollableState(node, scrollableType)) {
            continue;
        }
        const key = resolveScrollableStateKey(node, scrollableType, orderByGroupAndType);
        const distanceFromBottom = node.scrollHeight - (node.scrollTop + node.clientHeight);
        const distanceFromRight = node.scrollWidth - (node.scrollLeft + node.clientWidth);
        state.set(key, {
            scrollTop: node.scrollTop,
            scrollLeft: node.scrollLeft,
            stickToBottom: distanceFromBottom <= SCROLL_EDGE_TOLERANCE_PX,
            stickToRight: distanceFromRight <= SCROLL_EDGE_TOLERANCE_PX
        });
    }
    return state.size > 0 ? state : null;
};

export const applyKeyedScrollableState = (container: Element, state: Map<string, KeyedScrollState>): Set<string> => {
    const appliedKeys = new Set<string>();
    if (state.size === 0) {
        return appliedKeys;
    }
    const nodes = collectScrollableNodes(container);
    const orderByGroupAndType = new Map<string, number>();
    for (const node of nodes) {
        const scrollableType = resolveScrollableType(node);
        if (!scrollableType) {
            continue;
        }
        const key = resolveScrollableStateKey(node, scrollableType, orderByGroupAndType);
        const stored = state.get(key);
        if (!stored) {
            continue;
        }
        appliedKeys.add(key);
        if (stored.stickToBottom) {
            scrollNodeToBottom(node);
        } else {
            const maxTop = Math.max(0, node.scrollHeight - node.clientHeight);
            node.scrollTop = clampNumber(stored.scrollTop, 0, maxTop);
        }
        if (stored.stickToRight) {
            node.scrollLeft = node.scrollWidth;
        } else {
            const maxLeft = Math.max(0, node.scrollWidth - node.clientWidth);
            node.scrollLeft = clampNumber(stored.scrollLeft, 0, maxLeft);
        }
    }
    return appliedKeys;
};

export const applyKeyedScrollableStateWithBottomDefault = (container: Element, state: Map<string, KeyedScrollState> | null, bottomDefaultNode: HTMLElement): void => {
    const targetKey = resolveScrollableStateKeyForTarget(container, bottomDefaultNode);
    const appliedKeys = state ? applyKeyedScrollableState(container, state) : new Set<string>();
    if (targetKey === null || !appliedKeys.has(targetKey)) {
        scrollNodeToBottom(bottomDefaultNode);
    }
};
