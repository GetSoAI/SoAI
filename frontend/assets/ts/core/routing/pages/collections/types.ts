/* SoAI - Shared routing collections contracts [frontend/assets/ts/core/routing/pages/collections/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { CollectionConfig } from '@core/collectionpage/types.ts';
import type { GenerateStandardHeaderOptions } from '@core/routing/pages/pagetypes/public.ts';

type EventHandler = (eventObject: Event) => void;
type DelegatedHandler = (eventObject: Event, target: Element) => void;

interface ActionHandlerConfig {
    selector: string;
    handler: (eventObject: Event) => void;
    event?: string | undefined;
    preventDefault?: boolean | undefined;
    stopPropagation?: boolean | undefined;
    optional?: boolean | undefined;
}

interface DelegatedHandlerConfig {
    container: string;
    selector: string;
    handler: DelegatedHandler;
    event?: string | undefined;
}

type HeaderConfig = GenerateStandardHeaderOptions & {
    searchEnabled?: boolean | undefined;
};

interface HeaderMetadata {
    searchEnabled: boolean;
}

interface LayoutConfig {
    headerConfig: HeaderConfig;
    content?: string | undefined;
}

interface CollectionLayout {
    header?: HeaderConfig | null;
    headerMetadata?: HeaderMetadata | null;
    content?: string | undefined;
    filters?: Record<string, string> | null;
    actions?: ActionHandlerConfig[] | undefined;
    delegated?: DelegatedHandlerConfig[] | undefined;
}

type RawCollectionLayout = CollectionLayout;

interface ResolvedCollectionLayout {
    header: HeaderConfig | null;
    headerMetadata: HeaderMetadata | null;
    content: string;
    filters: Record<string, string> | null;
    actions: ActionHandlerConfig[];
    delegated: DelegatedHandlerConfig[];
}

interface ManagerConfig extends CollectionConfig {
    searchPlaceholder?: string | undefined;
}

interface CollectionEventBindingContext {
    resolveHostContainer(): HTMLElement;
    query(selector: string, context?: Element | Document | null): Element[];
    on(target: EventTarget, event: string, handler: EventHandler, options?: AddEventListenerOptions): () => void;
}

export type { ActionHandlerConfig, CollectionLayout, CollectionEventBindingContext, DelegatedHandler, DelegatedHandlerConfig, EventHandler, HeaderConfig, HeaderMetadata, LayoutConfig, ManagerConfig, RawCollectionLayout, ResolvedCollectionLayout };
