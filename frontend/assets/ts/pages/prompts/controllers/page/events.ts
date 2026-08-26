/* SoAI - Prompts page events [frontend/assets/ts/pages/prompts/controllers/page/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import type { SaveController } from '@core/save/public.ts';
import { isElementNode } from '@core/typeGuards.ts';
import type { PromptsPageEventsHost } from '@pages/prompts/controllers/page/contracts.ts';

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
        terminateHandledPromise(save.requestSave());
    }
};

const setupPromptsPageNonClickEvents = (host: PromptsPageEventsHost, save: SaveController, actionRoots: readonly HTMLElement[], signal: AbortSignal): void => {
    host.owners.collectionLayout.setupEventListeners();
    for (const root of actionRoots) {
        const handlePromptKeydown = (event: Event): void => handleKeydown(host, save, event);
        root.addEventListener('keydown', handlePromptKeydown, { signal });
    }
};

export { setupPromptsPageNonClickEvents };
export type { PromptsPageEventsHost };
