/* SoAI - Shared frontend DOM typed elements [frontend/assets/ts/core/dom/typedElements.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { narrowButton, narrowForm, narrowInput, narrowSelect, narrowTable, narrowTableSection, narrowTextarea } from '@core/dom/narrowElement.ts';

interface ElementResolver {
    requireHTMLElement(selector: string, context?: Element): HTMLElement;
}

const requireInputElement = (resolver: ElementResolver, selector: string, label: string, scopeContext?: Element): HTMLInputElement => narrowInput(resolver.requireHTMLElement(selector, scopeContext), label);

const requireTextareaElement = (resolver: ElementResolver, selector: string, label: string, scopeContext?: Element): HTMLTextAreaElement => narrowTextarea(resolver.requireHTMLElement(selector, scopeContext), label);

const requireButtonElement = (resolver: ElementResolver, selector: string, label: string, scopeContext?: Element): HTMLButtonElement => narrowButton(resolver.requireHTMLElement(selector, scopeContext), label);

const requireSelectElement = (resolver: ElementResolver, selector: string, label: string, scopeContext?: Element): HTMLSelectElement => narrowSelect(resolver.requireHTMLElement(selector, scopeContext), label);

const requireFormElement = (resolver: ElementResolver, selector: string, label: string, scopeContext?: Element): HTMLFormElement => narrowForm(resolver.requireHTMLElement(selector, scopeContext), label);

const requireTableElement = (resolver: ElementResolver, selector: string, label: string, scopeContext?: Element): HTMLTableElement => narrowTable(resolver.requireHTMLElement(selector, scopeContext), label);

const requireTableSectionElement = (resolver: ElementResolver, selector: string, label: string, scopeContext?: Element): HTMLTableSectionElement => narrowTableSection(resolver.requireHTMLElement(selector, scopeContext), label);

export { requireButtonElement, requireFormElement, requireInputElement, requireSelectElement, requireTableElement, requireTableSectionElement, requireTextareaElement };
export type { ElementResolver };
