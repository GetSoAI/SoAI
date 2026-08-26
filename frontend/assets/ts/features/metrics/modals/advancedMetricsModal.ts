/* SoAI - Metrics advanced modal definition and behavior [frontend/assets/ts/features/metrics/modals/advancedMetricsModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { isClipboardSupported } from '@core/clipboard.ts';
import { dom } from '@core/dom/dom.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { renderModalFooterActionButton, renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import { MODAL_HEADER_CLOSE_SELECTOR } from '@core/modals/headerButtons.ts';
import { requireModalPresenter, type ModalBinder, type ModalDefinition } from '@core/modals/modalPresenter.ts';
import { createModalElement } from '@core/modals/scaffoldDom.ts';
import { renderModalBody, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';
import type { ModalOpenOptions } from '@core/modals/types.ts';
import { modalUiId, modalUiSelector } from '@core/modals/uiIds.ts';
import { showNotification } from '@core/ui/notifications/notifications.ts';
import { copyTextWithBrowserClipboardFeedback } from '@core/ui/notifications/clipboardCopy.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { renderMetricsAdvancedModalContent } from '@features/metrics/modals/advancedMetricsContent.ts';
import { METRICS_ADVANCED_MODAL_ID, METRICS_ADVANCED_REFRESH_EVENT } from '@features/metrics/modals/advancedMetricsConstants.ts';
import { requireActiveMetricsHost } from '@features/metrics/modals/advancedMetricsHost.ts';

const openAbortControllers: WeakMap<HTMLElement, AbortController> = new WeakMap();

const setModalCopyText = (modal: HTMLElement, value: string): void => {
    dom.setData(modal, 'metricsAdvancedCopyText', value);
};

const getModalCopyText = (modal: HTMLElement): string => dom.getData(modal, 'metricsAdvancedCopyText') ?? '';

const resolveMetricsAdvancedSearchInput = (modal: HTMLElement): HTMLInputElement | null => {
    const input = dom.resolve(modalUiSelector(METRICS_ADVANCED_MODAL_ID, 'search'), modal);
    return input instanceof HTMLInputElement ? input : null;
};

const copyMetricsAdvancedInventory = async (modal: HTMLElement): Promise<void> => {
    const inventoryText = getModalCopyText(modal);
    if (!inventoryText) {
        return;
    }
    try {
        await copyTextWithBrowserClipboardFeedback(
            {
                showNotification: (message, type, duration): void => {
                    showNotification(message, type, duration);
                }
            },
            {
                text: inventoryText,
                successMessage: i18n.t('common.clipboard.copied'),
                errorMessage: i18n.t('common.clipboard.copyFailed'),
                unavailableMessage: i18n.t('common.clipboard.copyUnavailable'),
                duration: 3000,
                preserveText: true
            }
        );
    } catch (error) {
        errorHandler.error('MetricsAdvancedModal', 'Failed to copy advanced metrics inventory', ensureError(error));
    }
};

const bindMetricsAdvancedModal = (modal: HTMLElement): ModalBinder => {
    const abortController = new AbortController();
    const { signal } = abortController;
    const modalId = METRICS_ADVANCED_MODAL_ID;
    const copySelector = modalUiSelector(modalId, 'copy');

    const refreshClipboardState = (): void => {
        const button = dom.resolve(copySelector, modal);
        if (!(button instanceof HTMLButtonElement)) {
            throw new Error('Metrics advanced copy button is missing');
        }
        const supported = isClipboardSupported();
        button.disabled = !supported;
        if (!supported) {
            setTooltipText(button, i18n.t('common.clipboard.copyUnavailable'));
        } else {
            setTooltipText(button, '');
        }
    };

    const handleCopyClick = (event: Event): void => {
        if (!(event instanceof MouseEvent)) {
            return;
        }
        const target = event.target;
        if (!(target instanceof Element)) {
            return;
        }
        const copyButton = target.closest(copySelector);
        if (!(copyButton instanceof HTMLButtonElement)) {
            return;
        }
        event.preventDefault();
        event.stopPropagation();
        if (copyButton.disabled) {
            showNotification(i18n.t('common.clipboard.copyUnavailable'), 'warning', 4000);
            return;
        }
        terminateHandledPromise(copyMetricsAdvancedInventory(modal));
    };

    modal.addEventListener('click', handleCopyClick, { signal });
    refreshClipboardState();

    const handleRefresh = (): void => {
        const existing = openAbortControllers.get(modal) ?? null;
        if (!existing) {
            return;
        }
        const activeElement = dom.getActiveElement();
        const searchInput = resolveMetricsAdvancedSearchInput(modal);
        const query = searchInput?.value ?? '';
        const shouldRestoreFocus = searchInput instanceof HTMLInputElement && activeElement === searchInput;
        const selectionStart = searchInput?.selectionStart ?? query.length;
        const selectionEnd = searchInput?.selectionEnd ?? query.length;
        existing.abort();
        const nextController = new AbortController();
        openAbortControllers.set(modal, nextController);
        setModalCopyText(modal, '');
        const host = requireActiveMetricsHost();
        const rendered = renderMetricsAdvancedModalContent(modal, host, { placeholder: i18n.t('common.notAvailableShort'), query }, nextController.signal);
        setModalCopyText(modal, rendered.inventory.copyText);
        if (shouldRestoreFocus) {
            const nextSearchInput = resolveMetricsAdvancedSearchInput(modal);
            if (nextSearchInput) {
                nextSearchInput.focus();
                nextSearchInput.setSelectionRange(selectionStart, selectionEnd);
            }
        }
    };

    modal.addEventListener(METRICS_ADVANCED_REFRESH_EVENT, handleRefresh, { signal });

    return {
        dispose: () => {
            const existing = openAbortControllers.get(modal) ?? null;
            if (existing) {
                existing.abort();
                openAbortControllers.delete(modal);
            }
            abortController.abort();
        }
    };
};

const createMetricsAdvancedModalDefinition = (): ModalDefinition => {
    const modalId = METRICS_ADVANCED_MODAL_ID;
    const contentId = modalUiId(modalId, 'content');
    const copyButtonId = modalUiId(modalId, 'copy');

    return {
        id: modalId,
        layout: 'lg',
        initialFocusSelector: MODAL_HEADER_CLOSE_SELECTOR,
        createElement: (_options: ModalOpenOptions): HTMLElement => {
            const closeLabel = i18n.t('common.close');
            const copyLabel = i18n.t('common.copy');
            const advancedMetricsTitle = i18n.t('metrics.advanced.modalTitle');
            const header = renderStandardModalHeader({ modalId, title: advancedMetricsTitle, description: i18n.t('common.modalDescriptions.metricsAdvanced'), closeLabel });
            const body = renderModalBody('', { id: contentId, className: 'modal-body--sectioned' });
            const footer = renderSplitModalFooter({
                left: renderModalFooterCloseButton({ modalId, text: closeLabel }),
                right: renderModalFooterActionButton({ id: copyButtonId, text: copyLabel, variant: 'primary' })
            });
            return createModalElement({ id: modalId, rootAttributes: { 'data-page-scope': 'metrics' }, header, body, footer });
        },
        bind: (modal) => bindMetricsAdvancedModal(modal),
        onOpen: (modal: HTMLElement): void => {
            const existing = openAbortControllers.get(modal) ?? null;
            if (existing) {
                existing.abort();
            }
            const nextController = new AbortController();
            openAbortControllers.set(modal, nextController);
            setModalCopyText(modal, '');
            const host = requireActiveMetricsHost();
            const rendered = renderMetricsAdvancedModalContent(modal, host, { placeholder: i18n.t('common.notAvailableShort'), query: '' }, nextController.signal);
            setModalCopyText(modal, rendered.inventory.copyText);
        },
        onClose: (modal: HTMLElement): void => {
            const existing = openAbortControllers.get(modal) ?? null;
            if (existing) {
                existing.abort();
                openAbortControllers.delete(modal);
            }
            setModalCopyText(modal, '');
        }
    };
};

const METRICS_MODAL_DEFINITIONS: readonly ModalDefinition[] = Object.freeze([createMetricsAdvancedModalDefinition()]);

const openMetricsAdvancedModal = (options: ModalOpenOptions = {}): void => {
    requireModalPresenter().open(METRICS_ADVANCED_MODAL_ID, options);
};

const refreshMetricsAdvancedModalIfOpen = (): void => {
    const presenter = requireModalPresenter();
    if (!presenter.isOpen(METRICS_ADVANCED_MODAL_ID)) {
        return;
    }
    const modal = presenter.requireElement(METRICS_ADVANCED_MODAL_ID);
    modal.dispatchEvent(new Event(METRICS_ADVANCED_REFRESH_EVENT));
};

export { METRICS_ADVANCED_MODAL_ID, METRICS_MODAL_DEFINITIONS, openMetricsAdvancedModal, refreshMetricsAdvancedModalIfOpen };
