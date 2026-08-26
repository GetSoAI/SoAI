/* SoAI - Shared client data hub effects [frontend/assets/ts/core/data/clientdatahub/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CollectionsStore } from '@core/CollectionsStore.ts';
import { ensureArray } from '@core/normalize.ts';
import { createEmptyDiff } from '@core/data/clientdatahub/actions.ts';
import type { ResourceDiff, ResourceIncomingValue, ResourceItem, ResourceOperation } from '@core/data/clientdatahub/types.ts';

interface ResourceOperationApplyContext {
    store: CollectionsStore<ResourceItem>;
    fingerprints: Map<string, string>;
    normalize: (item: ResourceIncomingValue) => ResourceItem;
    trackBy: (item: ResourceItem) => string | null;
    fingerprint: (item: ResourceItem, raw?: ResourceIncomingValue) => string;
}

interface ResourceOperationApplyResult {
    mutated: boolean;
    diff: ResourceDiff;
    fingerprints: Map<string, string>;
}

const applyReplaceOperation = (items: ResourceItem[], diff: ResourceDiff, context: ResourceOperationApplyContext): { mutated: boolean; fingerprints: Map<string, string> } => {
    const nextFingerprints = new Map<string, string>();
    const normalizedItems: ResourceItem[] = [];
    const seenIds = new Set<string>();

    for (const entry of ensureArray(items)) {
        const normalized = context.normalize(entry);
        const id = context.trackBy(normalized);
        if (!id) {
            continue;
        }
        const fingerprint = context.fingerprint(normalized, entry);
        const previous = context.fingerprints.get(id);
        if (!previous) {
            diff.added.push(id);
        } else if (previous !== fingerprint) {
            diff.updated.push(id);
        }
        nextFingerprints.set(id, fingerprint);
        normalizedItems.push(normalized);
        seenIds.add(id);
    }

    for (const id of context.fingerprints.keys()) {
        if (!seenIds.has(id)) {
            diff.removed.push(id);
        }
    }

    context.store.replace(normalizedItems);
    return {
        mutated: normalizedItems.length > 0 || diff.removed.length > 0,
        fingerprints: nextFingerprints
    };
};

const applyUpsertOperation = (item: ResourceItem | undefined, diff: ResourceDiff, context: ResourceOperationApplyContext): boolean => {
    if (!item) {
        return false;
    }
    const normalized = context.normalize(item);
    const id = context.trackBy(normalized);
    if (!id) {
        return false;
    }

    const fingerprint = context.fingerprint(normalized, item);
    const previous = context.fingerprints.get(id);
    context.store.upsert(normalized);
    context.fingerprints.set(id, fingerprint);

    if (!previous) {
        diff.added.push(id);
        return true;
    }
    if (previous !== fingerprint) {
        diff.updated.push(id);
        return true;
    }
    return false;
};

const applyRemoveOperation = (id: string | number | undefined, diff: ResourceDiff, context: ResourceOperationApplyContext): boolean => {
    if (!id && id !== 0) {
        return false;
    }
    const identifier = String(id);
    if (!context.store.remove(identifier)) {
        return false;
    }
    context.fingerprints.delete(identifier);
    diff.removed.push(identifier);
    return true;
};

const applyResourceOperations = (operations: ResourceOperation[], context: ResourceOperationApplyContext): ResourceOperationApplyResult => {
    const diff = createEmptyDiff();
    let mutated = false;
    let fingerprints = context.fingerprints;

    for (const operation of operations) {
        if (operation.type === 'replace') {
            const replaceResult = applyReplaceOperation(operation.items ?? [], diff, {
                ...context,
                fingerprints
            });
            mutated = replaceResult.mutated || mutated;
            fingerprints = replaceResult.fingerprints;
        } else if (operation.type === 'upsert') {
            mutated = applyUpsertOperation(operation.item, diff, { ...context, fingerprints }) || mutated;
        } else if (operation.type === 'upsertMany') {
            for (const item of ensureArray(operation.items)) {
                mutated = applyUpsertOperation(item, diff, { ...context, fingerprints }) || mutated;
            }
        } else if (operation.type === 'remove') {
            mutated = applyRemoveOperation(operation.id, diff, { ...context, fingerprints }) || mutated;
        } else if (operation.type === 'removeMany') {
            for (const id of ensureArray(operation.ids)) {
                mutated = applyRemoveOperation(id, diff, { ...context, fingerprints }) || mutated;
            }
        }
    }

    return { diff, mutated, fingerprints };
};

export { applyResourceOperations };
export type { ResourceOperationApplyContext, ResourceOperationApplyResult };
