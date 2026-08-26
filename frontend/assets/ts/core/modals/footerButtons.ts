/* SoAI - Standardized modal footer buttons (close + actions) [frontend/assets/ts/core/modals/footerButtons.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import { normalizeModalId } from '@core/modals/guards.ts';
import type { HtmlAttributeValue } from '@core/modals/scaffold.ts';
import { EMPTY_UI_HTML, staticUiHtml, uiAttr, uiAttributes, uiHtml } from '@core/security/uiHtml.ts';

type FooterButtonVariant = 'neutral' | 'primary' | 'accent' | 'success' | 'warning' | 'danger' | 'violet';

const MODAL_FOOTER_DISMISS_ATTRIBUTE = 'data-modal-footer-dismiss';

const RESERVED_CLOSE_ATTRIBUTES = new Set<string>(['type', 'class', 'id', 'data-modal-close', MODAL_FOOTER_DISMISS_ATTRIBUTE, 'aria-label', 'title']);
const RESERVED_ACTION_ATTRIBUTES = new Set<string>(['type', 'class', 'id', 'data-action', 'disabled', 'aria-disabled', 'aria-hidden', 'aria-label', 'title']);

const resolveVariantClassName = (variant: FooterButtonVariant): string => ` ui-variant-${variant}`;

const renderExtraAttributes = (attributes: Readonly<Record<string, HtmlAttributeValue>> | undefined, reservedKeys: ReadonlySet<string>): TrustedHtml => {
    if (!attributes) {
        return EMPTY_UI_HTML;
    }
    const acceptedAttributes: Record<string, HtmlAttributeValue> = {};
    Object.entries(attributes).forEach(([key, value]) => {
        if (!key) {
            return;
        }
        if (reservedKeys.has(key)) {
            throw new Error(`Modal footer button attributes must not include reserved attribute "${key}"`);
        }
        if (typeof value === 'boolean') {
            if (value) {
                acceptedAttributes[key] = true;
            }
            return;
        }
        acceptedAttributes[key] = value;
    });
    return uiAttributes(acceptedAttributes);
};

const renderModalFooterDismissAttribute = (): TrustedHtml => {
    return uiAttributes({ [MODAL_FOOTER_DISMISS_ATTRIBUTE]: 'true' });
};

const renderModalFooterCloseButton = (options: { modalId: string; text: string; ariaLabel?: string | undefined; id?: string | undefined; className?: string | undefined; attributes?: Readonly<Record<string, HtmlAttributeValue>> | undefined }): ReturnType<typeof uiHtml> => {
    const modalId = normalizeModalId(options.modalId);
    const text = String(options.text ?? '').trim();
    if (!text) {
        throw new Error('renderModalFooterCloseButton requires non-empty text');
    }
    const ariaLabel = String(options.ariaLabel ?? text).trim();
    if (!ariaLabel) {
        throw new Error('renderModalFooterCloseButton requires a non-empty ariaLabel');
    }
    const variantClassName = resolveVariantClassName('neutral');
    const className = `ui-button${variantClassName}${options.className ? ` ${options.className}` : ''}`.trim();
    const idAttr = uiAttributes({ id: options.id });
    const extraAttributes = renderExtraAttributes(options.attributes, RESERVED_CLOSE_ATTRIBUTES);
    return uiHtml`<button type="button"${idAttr} class="${uiAttr(className)}" data-modal-close="${uiAttr(modalId)}"${renderModalFooterDismissAttribute()}${extraAttributes} aria-label="${uiAttr(ariaLabel)}" data-tooltip="${uiAttr(ariaLabel)}">${text}</button>`;
};

const renderModalFooterActionButton = (options: { text: string; ariaLabel?: string | undefined; id?: string | undefined; action?: string | undefined; variant?: FooterButtonVariant | undefined; className?: string | undefined; disabled?: boolean | undefined; ariaHidden?: boolean | undefined; attributes?: Readonly<Record<string, HtmlAttributeValue>> | undefined }): ReturnType<typeof uiHtml> => {
    const text = String(options.text ?? '').trim();
    if (!text) {
        throw new Error('renderModalFooterActionButton requires non-empty text');
    }
    const ariaLabel = String(options.ariaLabel ?? text).trim();
    if (!ariaLabel) {
        throw new Error('renderModalFooterActionButton requires a non-empty ariaLabel');
    }
    const variantClassName = resolveVariantClassName(options.variant ?? 'neutral');
    const className = `ui-button${variantClassName}${options.className ? ` ${options.className}` : ''}`.trim();

    const idAttr = uiAttributes({ id: options.id });
    const actionAttr = uiAttributes({ 'data-action': options.action });
    const disabledAttr = options.disabled === true ? staticUiHtml` disabled aria-disabled="true"` : EMPTY_UI_HTML;
    const hiddenAttr = options.ariaHidden === true ? staticUiHtml` aria-hidden="true"` : EMPTY_UI_HTML;
    const extraAttributes = renderExtraAttributes(options.attributes, RESERVED_ACTION_ATTRIBUTES);

    return uiHtml`<button type="button"${idAttr} class="${uiAttr(className)}"${actionAttr}${disabledAttr}${hiddenAttr}${extraAttributes} aria-label="${uiAttr(ariaLabel)}" data-tooltip="${uiAttr(ariaLabel)}">${text}</button>`;
};

export { renderModalFooterActionButton, renderModalFooterCloseButton, renderModalFooterDismissAttribute };
