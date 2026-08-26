/* SoAI - Shared frontend modal scaffold DOM [frontend/assets/ts/core/modals/scaffoldDom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { normalizeModalId, validateModalRootContract } from '@core/modals/guards.ts';
import { renderModalBody, renderModalFooter, renderModalScaffoldMarkup, renderStandardModalHeader, type HtmlAttributeValue, type ModalScaffoldConfig, type ModalScaffoldContent } from '@core/modals/scaffold.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { isHTMLElement } from '@core/typeGuards.ts';

interface CreateStandardModalElementOptions {
    title: ModalScaffoldContent;
    description?: ModalScaffoldContent | null | undefined;
    body: ModalScaffoldContent;
    footer: ModalScaffoldContent;
    contentClassName?: string | undefined;
    bodyClassName?: string | undefined;
    footerLayout?: string | undefined;
    footerClassName?: string | undefined;
    footerId?: string | undefined;
    closeLabel?: string | undefined;
    labelledBy?: string | undefined;
    rootAttributes?: Readonly<Record<string, HtmlAttributeValue>> | undefined;
}

const appendModalMarkupAndResolve = ({ bodyElement, modalId, markup }: { bodyElement: HTMLElement; modalId: string; markup: TrustedHtml }): HTMLElement => {
    const fragment = dom.createFragment(markup);
    dom.appendChild(bodyElement, fragment);
    dom.flush();

    const resolved = dom.resolve(`#${modalId}`);
    if (!(resolved instanceof HTMLElement)) {
        throw new Error('Failed to resolve created modal element');
    }
    validateModalRootContract(resolved, modalId);
    return resolved;
};

const createModalElement = (config: ModalScaffoldConfig): HTMLElement => {
    const bodyElement = dom.resolve('body');
    if (!isHTMLElement(bodyElement)) {
        throw new Error('Document body is unavailable');
    }

    const modalId = normalizeModalId(config.id);
    const markup = renderModalScaffoldMarkup(config);
    return appendModalMarkupAndResolve({ bodyElement, modalId, markup });
};

const createModalElementFromMarkup = (id: string, markup: TrustedHtml): HTMLElement => {
    const bodyElement = dom.resolve('body');
    if (!isHTMLElement(bodyElement)) {
        throw new Error('Document body is unavailable');
    }
    const modalId = normalizeModalId(id);
    return appendModalMarkupAndResolve({ bodyElement, modalId, markup });
};

const createStandardModalElement = (id: string, options: CreateStandardModalElementOptions): HTMLElement => {
    const modalId = normalizeModalId(id);
    const header = renderStandardModalHeader({
        modalId,
        title: options.title,
        ...(options.description !== undefined ? { description: options.description } : {}),
        ...(options.labelledBy ? { titleId: options.labelledBy } : {}),
        ...(options.closeLabel ? { closeLabel: options.closeLabel } : {})
    });
    const body = renderModalBody(options.body, { className: options.bodyClassName });
    const footerAttributes = options.footerId ? { id: options.footerId } : undefined;
    const footer = renderModalFooter(options.footer, { layout: options.footerLayout, className: options.footerClassName, attributes: footerAttributes });
    return createModalElement({
        id: modalId,
        labelledBy: options.labelledBy,
        rootAttributes: options.rootAttributes,
        header,
        body,
        footer,
        contentClassName: options.contentClassName
    });
};

export { createModalElement, createModalElementFromMarkup, createStandardModalElement };
