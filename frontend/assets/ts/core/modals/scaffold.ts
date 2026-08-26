/* SoAI - Shared frontend modal scaffold [frontend/assets/ts/core/modals/scaffold.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { MODAL_ROOT_CLASS, MODAL_ROOT_MARKER_ATTR, normalizeModalId } from '@core/modals/guards.ts';
import { MODAL_HEADER_BUTTON_ROLE_ATTRIBUTE, buildModalHeaderButtonClassName, renderModalHeaderButtonIcon } from '@core/modals/headerButtons.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { EMPTY_UI_HTML, joinUiHtml, uiAttr, uiAttributes, uiHtml, uiText } from '@core/security/uiHtml.ts';

type ModalScaffoldContent = string | TrustedHtml;
type HtmlAttributeValue = string | boolean | number;

interface ModalCloseButtonConfig {
    modalId: string;
    targetId?: string | undefined;
    label?: string | undefined;
    id?: string | undefined;
    className?: string | undefined;
    attributes?: Readonly<Record<string, HtmlAttributeValue>> | undefined;
    content?: ModalScaffoldContent | undefined;
}

interface ModalFooterSectionConfig {
    content: ModalScaffoldContent;
    align?: string | undefined;
    className?: string | undefined;
}

interface StandardModalHeaderConfig {
    modalId: string;
    title: ModalScaffoldContent;
    titleId?: string | undefined;
    description?: ModalScaffoldContent | null | undefined;
    descriptionId?: string | undefined;
    titleGroupClassName?: string | undefined;
    closeLabel?: string | undefined;
    closeTargetId?: string | undefined;
    headerClassName?: string | undefined;
    topClassName?: string | undefined;
    leading?: ModalScaffoldContent | undefined;
    trailing?: ModalScaffoldContent | undefined;
    sections?: ModalScaffoldContent | undefined;
    closeAttributes?: Readonly<Record<string, HtmlAttributeValue>> | undefined;
    closeId?: string | undefined;
    closeClassName?: string | undefined;
    closeContent?: ModalScaffoldContent | undefined;
    hideClose?: boolean | undefined;
}

interface SplitModalFooterConfig {
    left: ModalScaffoldContent;
    right?: ModalScaffoldContent | undefined;
    center?: ModalScaffoldContent | undefined;
    className?: string | undefined;
    id?: string | undefined;
}

interface ModalLoadingStateConfig {
    text: ModalScaffoldContent;
    hidden?: boolean | undefined;
    overlay?: boolean | undefined;
    className?: string | undefined;
    id?: string | undefined;
}

interface ModalScaffoldConfig {
    id: string;
    className?: string | undefined;
    hidden?: boolean | undefined;
    labelledBy?: string | undefined;
    overlayClassName?: string | undefined;
    contentClassName?: string | undefined;
    rootAttributes?: Readonly<Record<string, HtmlAttributeValue>> | undefined;
    contentAttributes?: Readonly<Record<string, HtmlAttributeValue>> | undefined;
    header: ModalScaffoldContent;
    body: ModalScaffoldContent;
    footer?: ModalScaffoldContent | undefined;
}

const toHtml = (value: ModalScaffoldContent): TrustedHtml => {
    if (typeof value === 'string') {
        return uiText(value);
    }
    return value;
};

const renderExtraAttributes = (attributes: Readonly<Record<string, HtmlAttributeValue>> | undefined): TrustedHtml => {
    if (!attributes) {
        return EMPTY_UI_HTML;
    }
    return uiAttributes(attributes);
};

const filterExtraAttributes = (attributes: Readonly<Record<string, HtmlAttributeValue>> | undefined, reservedKeys: ReadonlySet<string>): Readonly<Record<string, HtmlAttributeValue>> | undefined => {
    if (!attributes) {
        return undefined;
    }
    const result: Record<string, HtmlAttributeValue> = {};
    Object.entries(attributes).forEach(([key, value]) => {
        if (!key) {
            return;
        }
        if (reservedKeys.has(key)) {
            return;
        }
        result[key] = value;
    });
    return result;
};

const renderModalCloseButton = (config: ModalCloseButtonConfig): TrustedHtml => {
    const modalId = normalizeModalId(config.modalId);
    const targetId = config.targetId ? normalizeModalId(config.targetId) : modalId;
    const label = config.label ? String(config.label) : i18n.t('common.close');
    const defaultClassName = buildModalHeaderButtonClassName('close');
    const className = `${defaultClassName}${config.className ? ` ${config.className}` : ''}`;

    const reserved = new Set<string>(['aria-label', 'data-tooltip', 'type', 'class', 'id', 'data-modal-close', MODAL_HEADER_BUTTON_ROLE_ATTRIBUTE]);
    const extraAttributes = renderExtraAttributes(filterExtraAttributes(config.attributes, reserved));
    const identityAttributes = uiAttributes({ id: config.id });
    const roleAttributes = uiAttributes({ [MODAL_HEADER_BUTTON_ROLE_ATTRIBUTE]: 'close' });
    const content = config.content ? toHtml(config.content) : renderModalHeaderButtonIcon('close');

    return uiHtml`<button class="${uiAttr(className)}" type="button"${identityAttributes}${extraAttributes} aria-label="${uiAttr(label)}" data-tooltip="${uiAttr(label)}" data-modal-close="${uiAttr(targetId)}"${roleAttributes}>${content}</button>`;
};

const renderModalFooterSection = (config: ModalFooterSectionConfig): TrustedHtml => {
    const className = `modal-footer-section${config.align ? ` modal-footer-section--${config.align}` : ''}${config.className ? ` ${config.className}` : ''}`;
    return uiHtml`<div class="${uiAttr(className)}">${toHtml(config.content)}</div>`;
};

const renderDynamicSplitModalFooterContent = (config: { left: ModalScaffoldContent; right?: ModalScaffoldContent | undefined; center?: ModalScaffoldContent | undefined }): TrustedHtml => {
    const left = renderModalFooterSection({ align: 'left', content: config.left });
    const center = config.center ? renderModalFooterSection({ align: 'center', content: config.center }) : EMPTY_UI_HTML;
    const right = config.right ? renderModalFooterSection({ align: 'right', content: config.right }) : EMPTY_UI_HTML;
    return joinUiHtml([left, center, right]);
};

const renderStandardModalHeader = (config: StandardModalHeaderConfig): TrustedHtml => {
    const modalId = normalizeModalId(config.modalId);
    const titleId = config.titleId ? String(config.titleId) : modalUiId(modalId, 'title');
    const descriptionId = config.descriptionId ? String(config.descriptionId) : modalUiId(modalId, 'description');
    const closeLabel = config.closeLabel ? String(config.closeLabel) : i18n.t('common.close');
    const closeTargetId = config.closeTargetId ? normalizeModalId(config.closeTargetId) : modalId;

    const leading = config.leading ? toHtml(config.leading) : EMPTY_UI_HTML;
    const trailing = config.trailing ? toHtml(config.trailing) : EMPTY_UI_HTML;
    const hideClose = config.hideClose === true;
    const sections = config.sections ? toHtml(config.sections) : EMPTY_UI_HTML;
    const closeButton = hideClose
        ? EMPTY_UI_HTML
        : renderModalCloseButton({
              modalId,
              targetId: closeTargetId,
              label: closeLabel,
              id: config.closeId,
              className: config.closeClassName,
              attributes: config.closeAttributes,
              content: config.closeContent
          });
    const headerActions = hideClose ? EMPTY_UI_HTML : uiHtml`<div class="modal-header-actions">${closeButton}</div>`;

    const headerClassName = `modal-header${config.headerClassName ? ` ${config.headerClassName}` : ''}`;
    const topClassName = `modal-header-top${config.topClassName ? ` ${config.topClassName}` : ''}`;

    const shouldRenderDescription = config.description !== undefined && config.description !== null;
    const descriptionText = typeof config.description === 'string' ? config.description.trim() : '';
    const descriptionHiddenClassName = typeof config.description === 'string' && !descriptionText ? ' u-hidden' : '';
    const descriptionClassName = `modal-header-description${descriptionHiddenClassName}`;
    const descriptionMarkup = shouldRenderDescription ? uiHtml`<p id="${uiAttr(descriptionId)}" class="${uiAttr(descriptionClassName)}">${toHtml(config.description ?? '')}</p>` : EMPTY_UI_HTML;
    const titleMarkup = uiHtml`<div class="modal-header-title-copy"><h3 class="modal-title" id="${uiAttr(titleId)}">${toHtml(config.title)}</h3>${descriptionMarkup}</div>`;
    const titleGroup = config.titleGroupClassName ? uiHtml`<div class="${uiAttr(config.titleGroupClassName)}">${leading}${titleMarkup}${trailing}</div>` : joinUiHtml([leading, titleMarkup, trailing]);

    return uiHtml`<div class="${uiAttr(headerClassName)}"><div class="${uiAttr(topClassName)}">${titleGroup}${headerActions}</div>${sections}</div>`;
};

const renderModalBody = (content: ModalScaffoldContent, options: { className?: string | undefined; id?: string | undefined } = {}): TrustedHtml => {
    const className = `modal-body${options.className ? ` ${options.className}` : ''}`;
    return uiHtml`<div${uiAttributes({ id: options.id })} class="${uiAttr(className)}">${toHtml(content)}</div>`;
};

const renderModalLoadingState = (config: ModalLoadingStateConfig): TrustedHtml => {
    const classes = ['modal-loading-state'];
    if (config.overlay === true) {
        classes.push('modal-loading-state--overlay');
    }
    if (config.hidden === true) {
        classes.push('u-hidden');
    }
    if (config.className) {
        classes.push(config.className);
    }
    return uiHtml`<div${uiAttributes({ id: config.id })} class="${uiAttr(classes.join(' '))}" aria-live="polite"><span class="loading-spinner" aria-hidden="true"></span><span class="loading-text">${toHtml(config.text)}</span></div>`;
};

const renderSplitModalFooter = (config: SplitModalFooterConfig): TrustedHtml => {
    const className = `modal-footer modal-footer--split${config.className ? ` ${config.className}` : ''}`;
    const sections = renderDynamicSplitModalFooterContent({ left: config.left, ...(config.center ? { center: config.center } : {}), ...(config.right ? { right: config.right } : {}) });
    return uiHtml`<div${uiAttributes({ id: config.id })} class="${uiAttr(className)}">${sections}</div>`;
};

const renderModalFooter = (content: ModalScaffoldContent, options: { layout?: string | undefined; className?: string | undefined; attributes?: Readonly<Record<string, HtmlAttributeValue>> | undefined } = {}): TrustedHtml => {
    const className = `modal-footer${options.layout ? ` modal-footer--${options.layout}` : ''}${options.className ? ` ${options.className}` : ''}`;
    const reserved = new Set<string>(['class']);
    const extraAttributes = options.attributes ? renderExtraAttributes(filterExtraAttributes(options.attributes, reserved)) : EMPTY_UI_HTML;
    return uiHtml`<div class="${uiAttr(className)}"${extraAttributes}>${toHtml(content)}</div>`;
};

const renderModalScaffoldMarkup = (config: ModalScaffoldConfig): TrustedHtml => {
    const modalId = normalizeModalId(config.id);
    const hidden = config.hidden !== false;
    const ariaHidden = hidden ? 'true' : 'false';
    const labelledBy = config.labelledBy ? String(config.labelledBy) : modalUiId(modalId, 'title');

    const className = `${MODAL_ROOT_CLASS} ${modalId}${config.className ? ` ${String(config.className)}` : ''}${hidden ? ' u-hidden' : ''}`;
    const rootAttributes = renderExtraAttributes(config.rootAttributes);
    const contentAttributes = renderExtraAttributes(filterExtraAttributes(config.contentAttributes, new Set(['tabindex'])));
    const overlayClassName = `modal-overlay${config.overlayClassName ? ` ${String(config.overlayClassName)}` : ''}`;
    const contentClassName = `modal-content${config.contentClassName ? ` ${String(config.contentClassName)}` : ''}`;
    const footer = config.footer ? toHtml(config.footer) : EMPTY_UI_HTML;

    const rootMarkerAttribute = uiAttributes({ [MODAL_ROOT_MARKER_ATTR]: 'true' });
    return uiHtml`<div id="${uiAttr(modalId)}" class="${uiAttr(className)}"${rootMarkerAttribute}${rootAttributes} aria-hidden="${uiAttr(ariaHidden)}" role="dialog" aria-modal="true" aria-labelledby="${uiAttr(labelledBy)}"><div class="${uiAttr(overlayClassName)}"></div><div class="${uiAttr(contentClassName)}" tabindex="-1"${contentAttributes}>${toHtml(config.header)}${toHtml(config.body)}${footer}</div></div>`;
};

export { MODAL_ROOT_MARKER_ATTR, renderDynamicSplitModalFooterContent, renderModalBody, renderModalCloseButton, renderModalFooter, renderModalFooterSection, renderModalLoadingState, renderModalScaffoldMarkup, renderSplitModalFooter, renderStandardModalHeader };
export type { HtmlAttributeValue, ModalScaffoldConfig, ModalScaffoldContent };
