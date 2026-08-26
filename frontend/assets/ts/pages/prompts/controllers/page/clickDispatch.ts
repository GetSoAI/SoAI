/* SoAI - Prompts page click dispatch [frontend/assets/ts/pages/prompts/controllers/page/clickDispatch.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { i18n } from '@core/i18n/index.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { isPlainObject } from '@core/typeGuards.ts';
import { CONTENT_PREVIEW_MODAL_ID } from '@core/ui/modals/contentpreview/constants.ts';
import { requireContentPreviewModalService } from '@core/ui/modals/contentpreview/service.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import type { SaveController } from '@core/save/public.ts';
import { CONFIRMATION_MODAL_ID } from '@core/ui/modals/dialogs/ids.ts';
import { openNewPromptContentPreview, openPromptContentPreview, type OpenPromptPreviewOptions } from '@features/prompts/public.ts';
import { PROMPTS_ACTION_CARD_CANCEL_EDIT, PROMPTS_ACTION_CARD_COPY, PROMPTS_ACTION_CARD_DELETE, PROMPTS_ACTION_CARD_EDIT, PROMPTS_ACTION_CARD_OPEN, PROMPTS_ACTION_CARD_SAVE_EDIT, PROMPTS_ACTION_COLOR_SELECT, PROMPTS_ACTION_CREATE_PROMPT, PROMPTS_ACTION_DELETE_SELECTED, PROMPTS_ACTION_DESELECT_ALL, PROMPTS_ACTION_DOWNLOAD_SELECTED, PROMPTS_ACTION_DUPLICATE_SELECTED, PROMPTS_ACTION_SELECT_ALL, PROMPTS_ACTION_SORT_LIST, PROMPTS_ACTION_TOGGLE_SELECTION_MODE, PROMPTS_ACTION_TOGGLE_VIEW_MODE, type PromptsActionId } from '@pages/prompts/actions.ts';
import { createPromptsPromptPreviewHost } from '@pages/prompts/controllers/page/adapters.ts';
import { cancelEditing, createDraftPromptCard, downloadSelectedPrompts, duplicateSelected, handleCardColorSelection, startEditing } from '@pages/prompts/controllers/page/effects.ts';
import { copyPromptContent, deletePrompt, deleteSelectedPrompts } from '@pages/prompts/controllers/page/service.ts';
import type { PromptsRuntimeContext } from '@pages/prompts/controllers/page/contracts.ts';

type PromptsClickDispatchHost = PromptsRuntimeContext;

const openPromptPreview = (host: PromptsClickDispatchHost, save: SaveController, promptId: string | number, options: OpenPromptPreviewOptions = {}): Promise<boolean> => openPromptContentPreview(createPromptsPromptPreviewHost(host, host.components.promptEnhancer, save), promptId, options);

const dispatchPromptsClickAction = (host: PromptsClickDispatchHost, save: SaveController, actionId: PromptsActionId, actionElement: HTMLElement, event: Event): void => {
    void event;
    switch (actionId) {
        case PROMPTS_ACTION_CREATE_PROMPT:
            if (host.state.viewMode === 'list') {
                openNewPromptContentPreview(createPromptsPromptPreviewHost(host, host.components.promptEnhancer, save));
                save.notifyChanged();
                return;
            }
            createDraftPromptCard(host, save);
            return;
        case PROMPTS_ACTION_TOGGLE_VIEW_MODE:
            host.operations.toggleViewMode();
            return;
        case PROMPTS_ACTION_SORT_LIST:
            host.operations.sortList(actionElement);
            return;
        case PROMPTS_ACTION_TOGGLE_SELECTION_MODE:
            host.components.selectionController.toggleMode();
            return;
        case PROMPTS_ACTION_SELECT_ALL:
            if (actionElement instanceof HTMLInputElement && !actionElement.checked) {
                host.components.selectionController.deselectAll();
                return;
            }
            host.components.selectionController.selectAll();
            return;
        case PROMPTS_ACTION_DESELECT_ALL:
            host.components.selectionController.deselectAll();
            return;
        case PROMPTS_ACTION_DUPLICATE_SELECTED:
            terminateHandledPromise(duplicateSelected(host, save));
            return;
        case PROMPTS_ACTION_DOWNLOAD_SELECTED:
            downloadSelectedPrompts(host);
            return;
        case PROMPTS_ACTION_DELETE_SELECTED:
            terminateHandledPromise(
                (async (): Promise<void> => {
                    const ids = host.components.selectionController.list();
                    const count = ids.length;
                    if (count <= 0) {
                        return;
                    }

                    const confirmed = await requireDialogsService().showConfirmation({
                        title: i18n.t('prompts.modal.deleteMultiple.title'),
                        message: i18n.t('prompts.modal.deleteMultiple.message', {
                            count,
                            countId: modalUiId(CONFIRMATION_MODAL_ID, 'prompts-delete-count')
                        }),
                        messageAllowHTML: true,
                        description: i18n.t('prompts.modal.deleteMultiple.warning'),
                        confirmText: i18n.t('prompts.modal.deleteMultiple.confirm'),
                        cancelText: i18n.t('prompts.modal.deleteMultiple.cancel'),
                        variant: 'danger'
                    });
                    if (!confirmed) {
                        return;
                    }
                    await deleteSelectedPrompts(host, ids);
                })()
            );
            return;
        case PROMPTS_ACTION_COLOR_SELECT: {
            const pickerCandidate = actionElement.closest('.prompt-color-picker');
            const picker = pickerCandidate instanceof HTMLElement ? pickerCandidate : null;
            const context = picker?.dataset['colorContext'] ?? null;
            if (context === 'modal') {
                const modalRoot = host.owners.services.modals.requireElement(CONTENT_PREVIEW_MODAL_ID);
                const current = host.components.colorToolkit.normalize(modalRoot.dataset['selectedColor']);
                const requested = host.components.colorToolkit.normalize(actionElement.dataset['color']);
                const next = current && requested && current === requested ? null : requested;
                host.components.colorToolkit.applyToModal(modalRoot, next);
                const contentPreviewService = requireContentPreviewModalService();
                contentPreviewService.setTextSelectedColor(next);
                return;
            }
            const cardCandidate = actionElement.closest('.prompt-card, .prompts-list-row');
            const card = cardCandidate instanceof HTMLElement ? cardCandidate : null;
            const promptId = card?.dataset['promptId'] ?? null;
            if (!promptId) {
                throw new Error('Prompt card is missing data-prompt-id');
            }
            handleCardColorSelection(host, save, promptId, actionElement);
            return;
        }
        case PROMPTS_ACTION_CARD_OPEN: {
            const cardCandidate = actionElement.closest('.prompt-card, .prompts-list-row');
            const card = cardCandidate instanceof HTMLElement ? cardCandidate : null;
            const promptId = card?.dataset['promptId'] ?? null;
            if (!promptId) {
                throw new Error('Prompt card is missing data-prompt-id');
            }
            if (host.components.selectionController.isActive()) {
                host.components.selectionController.togglePrompt(promptId);
                return;
            }
            if (host.state.editingPromptId === promptId) {
                return;
            }
            const prompt = host.operations.findPromptById(promptId);
            if (!prompt) {
                throw new Error(`Prompt "${promptId}" is not available for viewing`);
            }
            terminateHandledPromise(openPromptPreview(host, save, promptId));
            save.notifyChanged();
            return;
        }
        case PROMPTS_ACTION_CARD_DELETE:
        case PROMPTS_ACTION_CARD_EDIT:
        case PROMPTS_ACTION_CARD_COPY:
        case PROMPTS_ACTION_CARD_CANCEL_EDIT:
        case PROMPTS_ACTION_CARD_SAVE_EDIT: {
            const cardCandidate = actionElement.closest('.prompt-card, .prompts-list-row');
            const card = cardCandidate instanceof HTMLElement ? cardCandidate : null;
            const promptId = card?.dataset['promptId'] ?? null;
            if (!promptId) {
                throw new Error('Prompt card is missing data-prompt-id');
            }
            switch (actionId) {
                case PROMPTS_ACTION_CARD_DELETE: {
                    const prompt = host.operations.findPromptById(promptId);
                    if (prompt) {
                        terminateHandledPromise(
                            (async (): Promise<void> => {
                                const nameRaw = isPlainObject(prompt) ? prompt['name'] : null;
                                const name = typeof nameRaw === 'string' && nameRaw.trim().length > 0 ? nameRaw.trim() : i18n.t('prompts.untitled');
                                const confirmed = await requireDialogsService().showConfirmation({
                                    title: i18n.t('prompts.modal.deletePrompt.title'),
                                    message: i18n.t('prompts.modal.deletePrompt.message'),
                                    description: name,
                                    confirmText: i18n.t('prompts.modal.deletePrompt.confirm'),
                                    cancelText: i18n.t('prompts.modal.deletePrompt.cancel'),
                                    variant: 'danger'
                                });
                                if (!confirmed) {
                                    return;
                                }
                                await deletePrompt(host, promptId);
                            })()
                        );
                    }
                    return;
                }
                case PROMPTS_ACTION_CARD_EDIT:
                    if (!card) {
                        throw new Error('Prompt card element is missing');
                    }
                    if (card.classList.contains('prompts-list-row')) {
                        terminateHandledPromise(openPromptPreview(host, save, promptId, { edit: true }));
                        save.notifyChanged();
                        return;
                    }
                    terminateHandledPromise(startEditing(host, save, promptId));
                    return;
                case PROMPTS_ACTION_CARD_COPY: {
                    const prompt = host.operations.findPromptById(promptId);
                    if (prompt && typeof prompt === 'object' && 'content' in prompt) {
                        const content = prompt['content'];
                        terminateHandledPromise(copyPromptContent(host, typeof content === 'string' ? content : null));
                    }
                    return;
                }
                case PROMPTS_ACTION_CARD_CANCEL_EDIT:
                    terminateHandledPromise(cancelEditing(host, save, promptId));
                    return;
                case PROMPTS_ACTION_CARD_SAVE_EDIT:
                    terminateHandledPromise(save.requestSave());
                    return;
            }
        }
    }
};
export { dispatchPromptsClickAction };
