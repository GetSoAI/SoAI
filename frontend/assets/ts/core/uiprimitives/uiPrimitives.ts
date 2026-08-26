/* SoAI - Frontend UI primitive ownership [frontend/assets/ts/core/uiprimitives/uiPrimitives.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { escapeAttribute, escapeHtml, iconResolver, notify } from '@core/uiprimitives/adapters.ts';
import type { Primitives } from '@core/uiprimitives/types.ts';
import { createCollectionLayoutFactory } from '@core/uiprimitives/service.ts';

const collection = createCollectionLayoutFactory({
    escapeHtml,
    escapeAttribute,
    iconResolver
});

const primitives: Primitives = Object.freeze({
    icons: Object.freeze({ get: iconResolver }),
    notify,
    escapeHtml,
    collection
});

export { createCollectionLayoutFactory, primitives };
export type { AriaProps, AttributeProps, BuildConfig, BuildResult, ButtonConfig, CardConfig, CollectionFactory, DatasetProps, EmptyStateConfig, GridConfig, IconConfig, IconOptions, NodeConfig, NotifyOptions, PageInstance, ParagraphConfig, Primitives, StatusLineConfig } from '@core/uiprimitives/types.ts';
