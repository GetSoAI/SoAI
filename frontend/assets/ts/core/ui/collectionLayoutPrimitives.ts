/* SoAI - Shared UI collection layout primitives [frontend/assets/ts/core/ui/collectionLayoutPrimitives.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveKernelService } from '@core/runtime/runtimeContext.ts';
import { hasFunctionProperty, isFunction, isObject } from '@core/typeGuards.ts';
import type { CollectionCardFactoryContract, CollectionFactory, CollectionLayoutBuilderContract, PageInstance } from '@core/uiprimitives/types.ts';

const PRIMITIVE_TOKEN = 'core.uiPrimitives';
type KernelServiceValue = ReturnType<typeof resolveKernelService>;
type CollectionPrimitiveCandidate = KernelServiceValue | CollectionFactory | CollectionLayoutBuilderContract | CollectionCardFactoryContract | CollectionPrimitivesRegistry | null | undefined;

interface CollectionPrimitivesRegistry {
    collection: CollectionFactory;
}

type CollectionLayoutBuilder = CollectionLayoutBuilderContract;

const isCollectionLayoutBuilder = (value: CollectionPrimitiveCandidate): value is CollectionLayoutBuilder => {
    if (!isObject(value)) return false;
    return hasFunctionProperty(value, 'build');
};

const isCollectionCardFactory = (value: CollectionPrimitiveCandidate): value is CollectionCardFactoryContract => {
    if (!isObject(value)) return false;
    return hasFunctionProperty(value, 'card') && hasFunctionProperty(value, 'section') && hasFunctionProperty(value, 'fragment') && hasFunctionProperty(value, 'button') && hasFunctionProperty(value, 'grid') && hasFunctionProperty(value, 'icon') && hasFunctionProperty(value, 'escapeHtml') && hasFunctionProperty(value, 'escapeAttribute') && hasFunctionProperty(value, 'getBuilder');
};

const isCollectionFactory = (value: CollectionPrimitiveCandidate): value is CollectionFactory => {
    if (!isObject(value)) return false;
    if (!hasFunctionProperty(value, 'createBuilder')) return false;
    if (!('cards' in value)) return false;
    const cardsValue = value.cards;
    return isObject(cardsValue) && hasFunctionProperty(cardsValue, 'createFactory');
};

const isCollectionPrimitivesRegistry = (value: CollectionPrimitiveCandidate): value is CollectionPrimitivesRegistry => {
    if (!isObject(value)) return false;
    if (!('collection' in value)) return false;
    const collection = value.collection;
    return isCollectionFactory(collection);
};

const getCollectionPrimitives = (): CollectionFactory => {
    const primitives = resolveKernelService(PRIMITIVE_TOKEN);
    if (!isCollectionPrimitivesRegistry(primitives)) {
        throw new TypeError('UI primitives module is unavailable');
    }
    return primitives.collection;
};

const requireCollectionPrimitives = (): CollectionFactory => {
    const primitives = getCollectionPrimitives();
    if (!isObject(primitives)) {
        throw new Error('UI primitives module is unavailable');
    }
    return primitives;
};

const createCollectionBuilder = (page: PageInstance): CollectionLayoutBuilder => {
    const collectionPrimitives = requireCollectionPrimitives();
    if (!isFunction(collectionPrimitives.createBuilder)) {
        throw new Error('Collection layout builder is unavailable');
    }
    const builder = collectionPrimitives.createBuilder(page);
    if (!isCollectionLayoutBuilder(builder)) {
        throw new Error('Collection layout builder must provide build()');
    }
    return builder;
};

const createCardFactory = (page: PageInstance): CollectionCardFactoryContract => {
    const collectionPrimitives = requireCollectionPrimitives();
    const cardsModule = collectionPrimitives['cards'];
    if (!isObject(cardsModule)) {
        throw new Error('Collection card factory is unavailable');
    }
    if (!isFunction(cardsModule.createFactory)) {
        throw new Error('Collection card factory is unavailable');
    }
    const cards = cardsModule.createFactory(page);
    if (!isCollectionCardFactory(cards)) {
        throw new Error('Collection card factory must provide rendering methods');
    }
    return cards;
};

export { createCollectionBuilder, getCollectionPrimitives, createCardFactory };
export type { CollectionLayoutBuilder };
