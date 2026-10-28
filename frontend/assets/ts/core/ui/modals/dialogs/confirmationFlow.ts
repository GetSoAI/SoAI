/* SoAI - Confirmation modal flow management for core.dialogs [frontend/assets/ts/core/ui/modals/dialogs/confirmationFlow.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { dom } from '@core/dom/dom.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { setModalFooterButtonLabel } from '@core/modals/footerButtons.ts';
import { MODAL_HEADER_CLOSE_SELECTOR } from '@core/modals/headerButtons.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { attachPendingOperationCloseGuard } from '@core/modals/closeGuard.ts';
import { runModalSession } from '@core/modals/modalSession.ts';
import { toTrustedHtml, type TrustedHtml } from '@core/security/public.ts';
import { EMPTY_UI_HTML } from '@core/security/uiHtml.ts';
import { getIconFromStringSync } from '@core/ui/icons/iconservice/public.ts';
import { DeferredButtonLoading } from '@core/ui/loadingbuttons/deferredLoadingButton.ts';
import { resolveConfirmationDom } from '@core/ui/modals/dialogs/confirmationDom.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';

interface NoticeSection {
    heading: string;
    items: readonly { label: string; detail: string }[];
}

type ConfirmationActionButton = {
    text: string;
    variantClassName: string;
    disabled: boolean;
    title: string | null;
    perform: (() => Promise<boolean> | boolean) | null;
    deferredBusy?: boolean;
};

type ConfirmationActionButtons = Readonly<{ first: ConfirmationActionButton | null; second: ConfirmationActionButton | null }>;

type ConfirmationDomConfig = {
    closeCompletes?: boolean;
    sections?: readonly NoticeSection[] | undefined;
    advisory?: { text: string; variant: 'info' | 'warning' } | undefined;
    fields?: HTMLElement | undefined;
    actionErrorText?: string | undefined;
    signal?: AbortSignal | undefined;
    title: string;
    typeTokens: readonly string[];
    icon: string | null;
    message: string;
    description: string | null;
    allowMessageHtml: boolean;
    allowDescriptionHtml: boolean;
    cancelText: string;
    actions: ConfirmationActionButtons;
};

interface ConfirmationFlowApi {
    show: (config: ConfirmationDomConfig) => Promise<boolean>;
}

const applyConfirmationModalClasses = (modal: HTMLElement, modalId: string, typeTokens: readonly string[]): void => {
    const preserved = new Set<string>(['ui-modal', modalId, 'u-hidden']);
    Array.from(modal.classList).forEach((className) => {
        if (className.endsWith('-modal') && !preserved.has(className)) {
            modal.classList.remove(className);
        }
    });
    modal.classList.add('ui-modal', modalId);
    typeTokens.forEach((token) => {
        modal.classList.add(`${token}-modal`);
    });
};

const createConfirmationFlow = (dependencies: { modalId: string }): ConfirmationFlowApi => {
    const show = async (config: ConfirmationDomConfig): Promise<boolean> => {
        const presenter = requireModalPresenter();
        return await runModalSession<boolean>({
            presenter,
            modalId: dependencies.modalId,
            onAlreadyOpen: 'replace',
            initialResult: false,
            signal: config.signal,
            initialize: ({ modal, signal, setResult, close }): { dispose: () => void } => {
                const domElements = resolveConfirmationDom(modal, dependencies.modalId);

                applyConfirmationModalClasses(modal, dependencies.modalId, config.typeTokens);

                const { titleElement, iconElement, messageElement, descriptionElement, cancelButton, action1Button, action2Button } = domElements;

                dom.setText(titleElement, config.title);

                if (config.icon) {
                    iconElement.classList.remove('u-hidden');
                    const iconHtml = getIconFromStringSync(config.icon, { size: 28 });
                    dom.setHTML(iconElement, iconHtml, { escape: false });
                } else {
                    iconElement.classList.add('u-hidden');
                    dom.setHTML(iconElement, EMPTY_UI_HTML, { escape: false });
                }

                if (config.allowMessageHtml) {
                    dom.setHTML(messageElement, toTrustedHtml(String(config.message)), { escape: false });
                } else {
                    dom.setText(messageElement, config.message);
                }

                if (config.description) {
                    descriptionElement.classList.remove('u-hidden');
                    if (config.allowDescriptionHtml) {
                        dom.setHTML(descriptionElement, toTrustedHtml(String(config.description)), { escape: false });
                    } else {
                        dom.setText(descriptionElement, config.description);
                    }
                } else {
                    descriptionElement.classList.add('u-hidden');
                    dom.setText(descriptionElement, '');
                }

                const advisory = dom.create('div', { className: 'confirmation-advisory form-disclaimer u-hidden' });
                const actionError = dom.create('div', { className: 'confirmation-advisory form-disclaimer form-disclaimer-error u-hidden', role: 'alert' });
                const sections = dom.create('div', { className: 'notice-sections u-hidden' });
                descriptionElement.after(...(config.fields ? [config.fields] : []), advisory, sections, actionError);
                if (config.sections?.length) {
                    sections.classList.remove('u-hidden');
                    sections.setAttribute('tabindex', '0');
                    for (const section of config.sections) {
                        const group = dom.create('section', { className: 'notice-section' });
                        const heading = dom.create('h3', { className: 'notice-section-heading' });
                        dom.setText(heading, section.heading);
                        const count = dom.create('span', { className: 'notice-section-count' });
                        dom.setText(count, String(section.items.length));
                        heading.append(count);
                        const list = dom.create('ul', { className: 'notice-section-list' });
                        for (const item of section.items) {
                            const row = dom.create('li', { className: 'notice-section-row' });
                            const label = dom.create('bdi', { className: 'notice-section-label' });
                            dom.setText(label, item.label);
                            row.append(label);
                            if (item.detail) {
                                const detail = dom.create('bdi', { className: 'notice-section-detail' });
                                dom.setText(detail, item.detail);
                                row.append(detail);
                            }
                            list.append(row);
                        }
                        group.append(heading, list);
                        sections.append(group);
                    }
                }
                if (config.advisory) {
                    dom.setText(advisory, config.advisory.text);
                    advisory.classList.remove('u-hidden');
                    advisory.classList.toggle('form-disclaimer-info', config.advisory.variant === 'info');
                }

                cancelButton.disabled = false;
                setModalFooterButtonLabel(cancelButton, config.cancelText);

                const configureActionButton = (element: HTMLButtonElement, button: ConfirmationActionButton | null): void => {
                    if (!button) {
                        element.classList.add('u-hidden');
                        element.setAttribute('aria-hidden', 'true');
                        element.disabled = true;
                        element.removeAttribute('aria-label');
                        setTooltipText(element, '');
                        dom.setText(element, '');
                        element.className = 'ui-button u-hidden';
                        return;
                    }
                    element.classList.remove('u-hidden');
                    element.removeAttribute('aria-hidden');
                    element.disabled = button.disabled;
                    setModalFooterButtonLabel(element, button.text, { tooltip: button.title });
                    element.className = `ui-button ${button.variantClassName}`.trim();
                };

                const action1 = config.actions.first;
                const action2 = config.actions.second;
                configureActionButton(action1Button, action1);
                configureActionButton(action2Button, action2);
                const deferredLoading = new DeferredButtonLoading();
                let actionPending = false;
                const detachCloseGuard = attachPendingOperationCloseGuard({ modal, isPending: () => actionPending });

                const cancel = (event: Event): void => {
                    event.preventDefault();
                    event.stopPropagation();
                    if (actionPending) return;
                    if (config.closeCompletes === true) setResult(true);
                    close('cancel');
                };
                cancelButton.addEventListener('click', cancel, { signal });
                if (config.closeCompletes === true) {
                    modal.addEventListener(
                        'click',
                        (event) => {
                            if (event.target instanceof Element && event.target.closest(MODAL_HEADER_CLOSE_SELECTOR)) cancel(event);
                        },
                        { signal }
                    );
                }

                const runAction = async (action: ConfirmationActionButton | null, button: HTMLButtonElement, reason: string): Promise<void> => {
                    if (!action || action.disabled || actionPending) {
                        return;
                    }
                    actionError.classList.add('u-hidden');
                    actionPending = true;
                    cancelButton.disabled = true;
                    action1Button.disabled = true;
                    action2Button.disabled = true;
                    if (action.deferredBusy === true) deferredLoading.begin(button);
                    try {
                        const allowed = action.perform ? await action.perform() : true;
                        if (signal.aborted) return;
                        if (allowed === false) {
                            return;
                        }
                        setResult(true);
                        close(reason);
                    } catch (error) {
                        const runtimeError = ensureError(error);
                        errorHandler.warn('Dialogs', 'Confirmation action failed', runtimeError);
                        if (!signal.aborted && config.actionErrorText) {
                            dom.setText(actionError, config.actionErrorText);
                            actionError.classList.remove('u-hidden');
                        }
                    } finally {
                        deferredLoading.settle();
                        actionPending = false;
                        if (!signal.aborted) {
                            cancelButton.disabled = false;
                            action1Button.disabled = action1?.disabled ?? true;
                            action2Button.disabled = action2?.disabled ?? true;
                            if (!modal.contains(dom.getActiveElement())) button.focus({ preventScroll: true });
                        }
                    }
                };

                const handleFirstAction = (event: Event): void => {
                    event.preventDefault();
                    event.stopPropagation();
                    terminateHandledPromise(runAction(action1, action1Button, 'action1'));
                };
                const handleSecondAction = (event: Event): void => {
                    event.preventDefault();
                    event.stopPropagation();
                    terminateHandledPromise(runAction(action2, action2Button, 'action2'));
                };
                action1Button.addEventListener('click', handleFirstAction, { signal });
                action2Button.addEventListener('click', handleSecondAction, { signal });

                return {
                    dispose: () => {
                        config.fields?.remove();
                        advisory.remove();
                        sections.remove();
                        actionError.remove();
                        detachCloseGuard();
                        deferredLoading.settle();
                    }
                };
            }
        });
    };

    return { show };
};

export { createConfirmationFlow };
export type { ConfirmationActionButton, ConfirmationActionButtons, ConfirmationDomConfig, ConfirmationFlowApi, NoticeSection, TrustedHtml };
