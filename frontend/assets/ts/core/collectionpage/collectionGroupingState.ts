/* SoAI - Collection grouping and expansion state [frontend/assets/ts/core/collectionpage/collectionGroupingState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface CollectionGroupResolution {
    key: string | number | null;
    heading: string | null;
}

interface CollectionGroupingHeadingsInput<TItem> {
    items: readonly TItem[];
    grouped: boolean;
    resolveItemId: (item: TItem) => string;
    resolveGroup: (item: TItem) => CollectionGroupResolution;
    firstHeading?: string | null;
}

class CollectionGroupingState<TItem> {
    readonly #headings = new Map<string, string | null>();

    headingFor(itemId: string): string | null {
        return this.#headings.get(itemId) ?? null;
    }

    clear(): void {
        this.#headings.clear();
    }

    applyHeadings(input: CollectionGroupingHeadingsInput<TItem>): string[] {
        const nextHeadings = new Map<string, string | null>();
        let currentKey: string | number | null = null;
        let isFirstItem = true;
        for (const item of input.items) {
            const itemId = input.resolveItemId(item);
            if (!itemId) {
                continue;
            }
            if (!input.grouped) {
                nextHeadings.set(itemId, isFirstItem && input.firstHeading ? input.firstHeading : null);
                isFirstItem = false;
                continue;
            }
            const resolution = input.resolveGroup(item);
            if (resolution.key === null) {
                nextHeadings.set(itemId, null);
                continue;
            }
            const isFirstInGroup = currentKey === null || resolution.key !== currentKey;
            nextHeadings.set(itemId, isFirstItem && input.firstHeading ? input.firstHeading : isFirstInGroup ? resolution.heading : null);
            if (isFirstInGroup) {
                currentKey = resolution.key;
            }
            isFirstItem = false;
        }
        const changedIds: string[] = [];
        for (const [itemId, heading] of nextHeadings) {
            if (this.#headings.get(itemId) !== heading) changedIds.push(itemId);
        }
        this.#headings.clear();
        for (const [itemId, heading] of nextHeadings) this.#headings.set(itemId, heading);
        return changedIds;
    }
}

export { CollectionGroupingState };
export type { CollectionGroupResolution, CollectionGroupingHeadingsInput };
