/* SoAI - Prompts page events [frontend/assets/ts/pages/prompts/controllers/page/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import type { SaveController } from '@core/save/public.ts';
import { isElementNode } from '@core/typeGuards.ts';
import type { PromptsPageEventsHost } from '@pages/prompts/controllers/page/contracts.ts';
import { cancelEditing } from '@pages/prompts/controllers/page/effects.ts';
import { hasPromptCardEditChanges } from '@pages/prompts/controllers/page/saveDirtyStateManager.ts';

const updatePromptEditDraft = (host: PromptsPageEventsHost, event: Event): void => {
    const target = event.target;
    if (!(target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement)) return;
    const field = target.dataset['field'];
    if (field !== 'name' && field !== 'content') return;
    const cardCandidate = target.closest('.prompt-card, .prompts-list-row');
    const card = cardCandidate instanceof HTMLElement ? cardCandidate : null;
    const promptId = card?.dataset['promptId'] ?? null;
    const editingDraft = host.state.editingDraft;
    if (!promptId || promptId !== host.state.editingPromptId || editingDraft?.promptId !== promptId) return;
    if (field === 'name') editingDraft.name = target.value;
    else editingDraft.content = target.value;
};

const handleKeydown = (host: PromptsPageEventsHost, save: SaveController, event: Event): void => {
    if (!(event instanceof KeyboardEvent)) {
        return;
    }
    const target = event.target;
    const element = isElementNode(target) ? target : null;
    if (event.key === 'Escape' && host.components.selectionController.isActive()) {
        host.components.selectionController.toggleMode();
        return;
    }
    if (event.key !== 'Enter' || (!event.ctrlKey && !event.metaKey) || !element) {
        return;
    }
    const cardCandidate = element.closest('.prompt-card, .prompts-list-row');
    const card = cardCandidate instanceof HTMLElement ? cardCandidate : null;
    const promptId = card?.dataset?.['promptId'] ?? null;
    if (promptId && promptId === host.state.editingPromptId && element.matches('[data-field="name"], [data-field="content"]')) {
        event.preventDefault();
        if (hasPromptCardEditChanges(host)) terminateHandledPromise(save.requestSave());
        else terminateHandledPromise(cancelEditing(host, save, promptId));
    }
};

const setupPromptsPageNonClickEvents = (host: PromptsPageEventsHost, save: SaveController, actionRoots: readonly HTMLElement[], signal: AbortSignal): void => {
    host.owners.collectionLayout.setupEventListeners();
    for (const root of actionRoots) {
        const handlePromptKeydown = (event: Event): void => handleKeydown(host, save, event);
        const handlePromptInput = (event: Event): void => updatePromptEditDraft(host, event);
        root.addEventListener('keydown', handlePromptKeydown, { signal });
        root.addEventListener('input', handlePromptInput, { signal, capture: true });
    }
};

export { setupPromptsPageNonClickEvents };
export type { PromptsPageEventsHost };
