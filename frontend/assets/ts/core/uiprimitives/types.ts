/* SoAI - Shared UI primitives contracts [frontend/assets/ts/core/uiprimitives/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import type { ActionHandlerConfig, CollectionLayout, DelegatedHandlerConfig, HeaderConfig } from '@core/routing/pages/collections/types.ts';

type MarkupContent = string | TrustedHtml;
type ClassValue = string | readonly ClassValue[] | null | undefined | false;
type EscapableValue = string | number | boolean | TrustedHtml | null | undefined;
type LayoutAttributeValue = string | boolean | number | undefined;
type LayoutNodeValue = MarkupContent | NodeConfig | ButtonConfig | CardConfig | EmptyStateConfig | GridConfig | readonly LayoutNodeValue[] | LayoutNodeFactory | null | undefined;
type LayoutNodeFactory = (builder: CollectionLayoutBuilderContract) => LayoutNodeValue;

interface AriaProps {
    [key: string]: LayoutAttributeValue;
}

interface AttributeProps {
    [key: string]: LayoutAttributeValue;
}

interface DatasetProps {
    [key: string]: LayoutAttributeValue;
}

interface NodeConfig {
    type?: string | undefined;
    tag?: string | undefined;
    id?: string | undefined;
    className?: string | undefined;
    hidden?: boolean | undefined;
    sizeClass?: string | undefined;
    role?: string | undefined;
    aria?: AriaProps | undefined;
    dataset?: DatasetProps | undefined;
    attributes?: AttributeProps | undefined;
    children?: LayoutNodeValue;
}

interface GridConfig extends NodeConfig {
    wrapperId?: string | undefined;
    wrapperClass?: string | undefined;
    emptyStates?: EmptyStateConfig[] | undefined;
}

interface IconOptions {
    className?: string | undefined;
    size?: string | number | undefined;
    [key: string]: string | boolean | number | null | undefined | AttributeProps;
}

interface IconConfig {
    name: string;
    options?: IconOptions | undefined;
}

interface NotifyOptions {
    duration?: number | undefined;
    [key: string]: string | boolean | number | null | undefined;
}

interface ParagraphConfig {
    id?: string | undefined;
    text?: string | undefined;
    raw?: boolean | undefined;
}

interface EmptyStateConfig extends NodeConfig {
    icon?: string | IconConfig | undefined;
    title?: string | undefined;
    titleId?: string | undefined;
    description?: string | ParagraphConfig | undefined;
    descriptionId?: string | undefined;
    body?: MarkupContent | undefined;
    actions?: ButtonConfig[] | undefined;
    contentClass?: string | undefined;
}

interface ButtonConfig {
    html?: MarkupContent | undefined;
    tag?: 'button' | 'a' | undefined;
    id?: string | undefined;
    className?: string | undefined;
    href?: string | undefined;
    target?: string | undefined;
    rel?: string | undefined;
    type?: string | undefined;
    disabled?: boolean | undefined;
    attributes?: AttributeProps | undefined;
    aria?: AriaProps | undefined;
    dataset?: DatasetProps | undefined;
    label?: string | undefined;
    content?: MarkupContent | undefined;
    icon?: string | IconConfig | undefined;
}

interface CardConfig extends NodeConfig {
    actions?: (string | ButtonConfig)[] | undefined;
    actionsWrapperClass?: string | undefined;
    sections?: LayoutNodeValue[] | undefined;
    content?: LayoutNodeValue;
    statusLine?: StatusLineConfig | undefined;
    includeCollectionRoot?: boolean | undefined;
}

interface StatusLineConfig {
    tag?: string | undefined;
    className?: string | undefined;
    dataset?: DatasetProps | undefined;
    attributes?: AttributeProps | undefined;
    aria?: AriaProps | undefined;
}

interface BuildConfig {
    header?: HeaderConfig | null | undefined;
    sections?: LayoutNodeValue[] | undefined;
    filters?: Record<string, string> | null | undefined;
    actions?: ActionHandlerConfig[] | undefined;
    delegated?: DelegatedHandlerConfig[] | undefined;
}

type BuildResult = CollectionLayout;

interface PageInstance {
    pageId?: string | undefined;
    dom?:
        | {
              createFragment: (markup: TrustedHtml) => DocumentFragment;
          }
        | undefined;
    sanitizeClassName?: ((className: string, type: string) => string) | undefined;
}

interface Primitives {
    icons: {
        get: (name: string, options?: IconOptions) => TrustedHtml;
    };
    notify: (message: string, type?: string, options?: NotifyOptions) => void;
    escapeHtml: (value: string) => string;
    collection: CollectionFactory;
}

interface CollectionLayoutBuilderContract {
    combineClasses: (...values: ClassValue[]) => string;
    build: (config?: BuildConfig) => BuildResult;
    resolveNode: (node: LayoutNodeValue) => string;
    fragment: (config?: NodeConfig) => string;
    section: (config?: NodeConfig) => string;
    grid: (config?: GridConfig) => string;
    emptyState: (config?: EmptyStateConfig) => string;
    button: (config?: ButtonConfig | string | null) => string;
    card: (config?: CardConfig) => string;
    escapeHtml: (value: string) => string;
    escapeAttributeValue: (value: EscapableValue) => string;
    resolveIcon: (icon: string | IconConfig | undefined) => string;
}

interface CollectionCardFactoryContract {
    card: (config?: CardConfig) => string;
    section: (config?: NodeConfig) => string;
    fragment: (config?: NodeConfig | string) => string;
    button: (config?: ButtonConfig) => string;
    grid: (config?: GridConfig) => string;
    icon: (name: string | IconConfig, options?: IconOptions) => string;
    escapeHtml: (value: EscapableValue) => string;
    escapeAttribute: (value: EscapableValue) => string;
    getBuilder: () => CollectionLayoutBuilderContract;
}

interface CollectionFactory {
    createBuilder: (page: PageInstance) => CollectionLayoutBuilderContract;
    cards: {
        createFactory: (page: PageInstance) => CollectionCardFactoryContract;
    };
}

export type { AriaProps, AttributeProps, BuildConfig, BuildResult, ButtonConfig, CardConfig, ClassValue, CollectionCardFactoryContract, CollectionFactory, CollectionLayoutBuilderContract, DatasetProps, EmptyStateConfig, EscapableValue, GridConfig, IconConfig, IconOptions, LayoutNodeFactory, LayoutNodeValue, MarkupContent, NodeConfig, NotifyOptions, PageInstance, ParagraphConfig, Primitives, StatusLineConfig };
