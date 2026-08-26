/* SoAI - Confirmation modal flow management for core.dialogs [frontend/assets/ts/core/ui/modals/dialogs/confirmationFlow.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { dom } from '@core/dom/dom.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { runModalSession } from '@core/modals/modalSession.ts';
import { toTrustedHtml, type TrustedHtml } from '@core/security/public.ts';
import { EMPTY_UI_HTML } from '@core/security/uiHtml.ts';
import { getIconFromStringSync } from '@core/ui/icons/iconservice/public.ts';
import { resolveConfirmationDom } from '@core/ui/modals/dialogs/confirmationDom.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';

type ConfirmationActionButton = {
    text: string;
    variantClassName: string;
    disabled: boolean;
    title: string | null;
    perform: (() => Promise<boolean> | boolean) | null;
};

type ConfirmationActionButtons = Readonly<{ first: ConfirmationActionButton | null; second: ConfirmationActionButton | null }>;

type ConfirmationDomConfig = {
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

                cancelButton.disabled = false;
                dom.setText(cancelButton, config.cancelText);
                cancelButton.setAttribute('aria-label', config.cancelText);
                setTooltipText(cancelButton, config.cancelText);

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
                    setTooltipText(element, button.title);
                    dom.setText(element, button.text);
                    element.setAttribute('aria-label', button.text);
                    element.className = `ui-button ${button.variantClassName}`.trim();
                };

                const action1 = config.actions.first;
                const action2 = config.actions.second;
                configureActionButton(action1Button, action1);
                configureActionButton(action2Button, action2);

                const cancel = (event: Event): void => {
                    event.preventDefault();
                    event.stopPropagation();
                    close('cancel');
                };
                cancelButton.addEventListener('click', cancel, { signal });

                const runAction = async (action: ConfirmationActionButton | null, reason: string): Promise<void> => {
                    if (!action || action.disabled) {
                        return;
                    }
                    try {
                        const allowed = action.perform ? await action.perform() : true;
                        if (allowed === false) {
                            return;
                        }
                        setResult(true);
                        close(reason);
                    } catch (error) {
                        const runtimeError = ensureError(error);
                        errorHandler.warn('Dialogs', 'Confirmation action failed', runtimeError);
                    }
                };

                action1Button.addEventListener(
                    'click',
                    (event: Event): void => {
                        event.preventDefault();
                        event.stopPropagation();
                        terminateHandledPromise(runAction(action1, 'action1'));
                    },
                    { signal }
                );
                action2Button.addEventListener(
                    'click',
                    (event: Event): void => {
                        event.preventDefault();
                        event.stopPropagation();
                        terminateHandledPromise(runAction(action2, 'action2'));
                    },
                    { signal }
                );

                return { dispose: () => void 0 };
            }
        });
    };

    return { show };
};

export { createConfirmationFlow };
export type { ConfirmationActionButton, ConfirmationActionButtons, ConfirmationDomConfig, ConfirmationFlowApi, TrustedHtml };
