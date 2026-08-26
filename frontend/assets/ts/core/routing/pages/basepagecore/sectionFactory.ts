/* SoAI - Shared routing section factory [frontend/assets/ts/core/routing/pages/basepagecore/sectionFactory.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { err } from '@core/routing/pages/basepagecore/actions.ts';
import type { ElementOptions } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import type { CreateSectionOptions, GridPosition } from '@core/routing/pages/pagetypes/public.ts';
import { EMPTY_UI_HTML, uiAttr, uiHtml, uiText } from '@core/security/uiHtml.ts';
import { isHTMLElement } from '@core/typeGuards.ts';
import type { TrustedHtml } from '@core/security/public.ts';

const createPageSectionElement = (
    sectionId: string,
    options: CreateSectionOptions,
    dependencies: {
        createElement: (tagName: string, attributes?: ElementOptions) => HTMLElement;
        applyGridPosition: (element: HTMLElement, position: GridPosition) => void;
        updateHTML: (element: Element, html: TrustedHtml | string, options?: { escape?: boolean }) => void;
    }
): HTMLElement => {
    const title = options.title ?? i18n.t('common.section.defaultTitle');
    const subtitle = options.subtitle ?? '';
    const controls = options.controls ?? EMPTY_UI_HTML;
    const className = options.className ?? 'section';
    const position = options.position ?? null;
    const showSubtitle = options.showSubtitle ?? true;
    const loadingMessage = options.loadingText ?? i18n.t('ui.preloader.loading');
    const section = dependencies.createElement('div', { class: className, 'data-section-id': sectionId });
    if (!isHTMLElement(section)) {
        throw err('Section root must be an HTMLElement');
    }
    if (position) {
        dependencies.applyGridPosition(section, position);
    }
    const subtitleId = `${sectionId}-subtitle`;
    const contentId = `${sectionId}-content`;
    const statusLineId = `${sectionId}-status`;
    const subtitleSlot = showSubtitle ? uiHtml`<div class="section-subtitle" id="${uiAttr(subtitleId)}">${uiText(subtitle)}</div>` : EMPTY_UI_HTML;
    const statusLineSlot = sectionId === 'status' ? uiHtml`<div class="section-status-line" id="${uiAttr(statusLineId)}"></div>` : EMPTY_UI_HTML;
    const markup = uiHtml`<div class="section-header" data-section-handle="${uiAttr(sectionId)}"><div class="section-header-main"><div class="section-title">${uiText(title)}</div>${subtitleSlot}</div><div class="section-controls">${controls}</div></div><div class="section-content" id="${uiAttr(contentId)}"><div class="section-loading">${uiText(loadingMessage)}</div></div>${statusLineSlot}`;
    dependencies.updateHTML(section, markup, { escape: false });
    return section;
};

export { createPageSectionElement };
