/* SoAI - Shared frontend DOM public contracts [frontend/assets/ts/core/dom/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DomDatasetMap, DomPropertyMap, DomPropertyValue } from '@core/dom/propertyValues.ts';
import type { TrustedHtml } from '@core/security/public.ts';

export type DOMStyleMap = Record<string, string | null>;
export type DOMDatasetStringMap = Record<string, string>;

export type DOMQueryRoot = Element | Document | DocumentFragment;
export type DOMTarget = DOMQueryRoot | Window | string | null | undefined;
export type DOMContext = DOMQueryRoot | null | undefined;
export type DOMPlainRecord = DomPropertyMap | DomDatasetMap | DOMStyleMap | ElementOptions;
export type DOMRuntimeCandidate = string | number | boolean | bigint | symbol | Window | Node | NodeList | HTMLCollection | DOMPlainRecord | null | undefined | void;
export type DOMChildContent = Node | NodeList | HTMLCollection | string | readonly DOMChildContent[] | null | undefined;

export type DOMUpdate = { type: 'text'; value: string } | { type: 'html'; value: string } | { type: 'attribute'; attribute: string; value: string | null } | { type: 'style'; property: string; value: string | null } | { type: 'styles'; styles: Record<string, string | null> } | { type: 'addClass'; classes: string[] } | { type: 'removeClass'; classes: string[] } | { type: 'toggleClass'; className: string; force: boolean | null } | { type: 'replaceContent'; content: DocumentFragment | HTMLElement } | { type: 'appendChild'; children: Node[] } | { type: 'insertBefore'; children: Node[]; reference: Node | null } | { type: 'property'; property: string; value: DomPropertyValue } | { type: 'properties'; properties: DomPropertyMap } | { type: 'remove' } | { type: 'visibility'; visible: boolean };

export interface SetHTMLOptions {
    escape?: boolean;
    context?: DOMContext;
}

export interface ReplaceContentOptions {
    escape?: boolean;
    context?: DOMContext;
}

export interface ScrollStateEntry {
    element: HTMLElement;
    top: number;
    left: number;
}

export type ElementOptionValue = string | number | boolean | null | undefined | TrustedHtml | string[] | DOMStyleMap;

export interface ElementOptions {
    id?: string;
    class?: string | string[];
    className?: string | string[];
    textContent?: string;
    html?: TrustedHtml;
    style?: DOMStyleMap;
    dataset?: DOMDatasetStringMap;
    includeIdClass?: boolean;
    [key: string]: ElementOptionValue;
}

export interface PerformanceMetrics {
    totalUpdates: number;
    batchedUpdates: number;
    averageBatchSize: number;
}
