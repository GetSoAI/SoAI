/* SoAI - Collection group entry construction [frontend/assets/ts/core/collectionpage/collectionGroupEntry.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';

const COLLECTION_GROUP_ENTRY_CLASS = 'ui-collection-group-entry';
const COLLECTION_GROUP_SEPARATOR_CLASS = 'ui-collection-group-separator';
const COLLECTION_GROUP_TITLE_CLASSES: readonly string[] = ['ui-collection-group-title', 'surface-card'];

interface CollectionGroupEntryInput {
    card: HTMLElement;
    heading: string | null;
    identityAttribute: string;
}

const createCollectionGroupSeparator = (heading: string): HTMLElement => {
    const separator = dom.create('div', { className: COLLECTION_GROUP_SEPARATOR_CLASS });
    const title = dom.create('div', { className: [...COLLECTION_GROUP_TITLE_CLASSES], textContent: heading });
    separator.appendChild(title);
    return separator;
};

const renderCollectionGroupEntry = (input: CollectionGroupEntryInput): HTMLElement => {
    if (!input.heading) {
        return input.card;
    }
    const identity = input.card.getAttribute(input.identityAttribute);
    if (identity === null) {
        throw new Error(`Collection group entry requires ${input.identityAttribute} on the grouped card`);
    }
    const entry = dom.create('div', { className: COLLECTION_GROUP_ENTRY_CLASS });
    entry.setAttribute(input.identityAttribute, identity);
    entry.appendChild(createCollectionGroupSeparator(input.heading));
    entry.appendChild(input.card);
    return entry;
};

export { renderCollectionGroupEntry };
export type { CollectionGroupEntryInput };
