/* SoAI - Prompts picker modal rendering [frontend/assets/ts/features/prompts/picker/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { checkerboardService, dom } from '@core/dom/dom.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { PROMPTS_PICKER_ACTION_EDIT, PROMPTS_PICKER_ACTION_INSERT } from '@features/prompts/picker/actions.ts';
import type { PromptsPickerRenderInput } from '@features/prompts/picker/types.ts';
import type { PromptRecord } from '@features/prompts/promptRecords.ts';

const PROMPT_CARD_SELECTOR = '.prompts-picker-card';

const setStatus = (input: PromptsPickerRenderInput): void => {
    const { refs, state, visiblePrompts } = input;
    refs.status.hidden = false;
    if (state.loading) {
        refs.status.textContent = i18n.t('prompts.picker.loading');
        return;
    }
    if (state.errorMessage) {
        refs.status.textContent = state.errorMessage;
        return;
    }
    if (state.prompts.length === 0) {
        refs.status.textContent = i18n.t('prompts.picker.empty');
        return;
    }
    if (visiblePrompts.length === 0) {
        refs.status.textContent = i18n.t('prompts.picker.noMatches');
        return;
    }
    refs.status.hidden = true;
    refs.status.textContent = '';
};

const createPromptCard = (input: PromptsPickerRenderInput, prompt: PromptRecord): HTMLElement => {
    const documentRef = input.refs.root.ownerDocument;
    const card = documentRef.createElement('div');
    card.className = 'search-item search-item--card prompts-picker-card prompt-color-surface';
    card.dataset['action'] = PROMPTS_PICKER_ACTION_INSERT;
    card.dataset['promptId'] = prompt.id;
    card.dataset['selectedColor'] = prompt.color ?? '';
    if (prompt.color) {
        card.dataset['promptColor'] = prompt.color;
    }
    card.setAttribute('role', 'button');
    card.setAttribute('tabindex', '0');
    card.setAttribute('aria-label', prompt.name);
    setTooltipText(card, prompt.name);

    const content = documentRef.createElement('span');
    content.className = 'search-item-content';
    const header = documentRef.createElement('div');
    header.className = 'search-item-header';
    const title = documentRef.createElement('span');
    title.className = 'search-item-title';
    title.textContent = prompt.name;
    header.appendChild(title);
    const description = documentRef.createElement('div');
    description.className = 'search-item-description';
    description.textContent = prompt.content || i18n.t('prompts.picker.emptyContent');
    content.appendChild(header);
    content.appendChild(description);
    card.appendChild(content);

    const editButton = documentRef.createElement('button');
    editButton.type = 'button';
    editButton.className = 'ui-round-button ui-round-button--edit prompts-picker-edit';
    editButton.dataset['action'] = PROMPTS_PICKER_ACTION_EDIT;
    editButton.dataset['promptId'] = prompt.id;
    const editLabel = i18n.t('prompts.actions.editPrompt');
    editButton.setAttribute('aria-label', editLabel);
    setTooltipText(editButton, editLabel);
    dom.setHTML(editButton, input.getEditIcon(), { escape: false });
    card.appendChild(editButton);
    return card;
};

const renderPromptsPickerModal = (input: PromptsPickerRenderInput): void => {
    setStatus(input);
    const fragment = input.refs.root.ownerDocument.createDocumentFragment();
    for (const prompt of input.visiblePrompts) {
        fragment.appendChild(createPromptCard(input, prompt));
    }
    dom.replaceContent(input.refs.results, fragment);
    checkerboardService.applyCheckerboard(input.refs.results, PROMPT_CARD_SELECTOR);
};

export { renderPromptsPickerModal };
