/* SoAI - Shared frontend modal scaffold DOM [frontend/assets/ts/core/modals/scaffoldDom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { normalizeModalId, validateModalRootContract } from '@core/modals/guards.ts';
import { renderModalBody, renderModalFooter, renderModalScaffoldMarkup, renderStandardModalHeader, type HtmlAttributeValue, type ModalScaffoldConfig, type ModalScaffoldContent } from '@core/modals/scaffold.ts';
import type { TrustedHtml } from '@core/security/public.ts';

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

const parseModalMarkup = (modalId: string, markup: TrustedHtml): HTMLElement => {
    const fragment = dom.createFragment(markup);
    const resolved = fragment.firstElementChild;
    if (!(resolved instanceof HTMLElement) || fragment.childElementCount !== 1 || resolved.id !== modalId) {
        throw new Error(`Modal markup must contain exactly one root with id="${modalId}"`);
    }
    validateModalRootContract(resolved, modalId);
    return resolved;
};

const createModalElement = (config: ModalScaffoldConfig): HTMLElement => {
    const modalId = normalizeModalId(config.id);
    const markup = renderModalScaffoldMarkup(config);
    return parseModalMarkup(modalId, markup);
};

const createModalElementFromMarkup = (id: string, markup: TrustedHtml): HTMLElement => {
    const modalId = normalizeModalId(id);
    return parseModalMarkup(modalId, markup);
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
