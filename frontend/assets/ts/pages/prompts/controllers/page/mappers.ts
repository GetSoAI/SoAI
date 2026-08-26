/* SoAI - Prompts page control layer mapping [frontend/assets/ts/pages/prompts/controllers/page/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { SelectionManager } from '@pages/prompts/controllers/SelectionManager.ts';
import type { PromptsRuntimeContext } from '@pages/prompts/controllers/page/contracts.ts';

type PromptsSelectionManagerHost = Pick<PromptsRuntimeContext, 'owners' | 'operations'>;

const createPromptsSelectionManager = (host: PromptsSelectionManagerHost, setElementVisibility: (element: Element | undefined, visible: boolean) => void): SelectionManager => {
    return new SelectionManager({
        getFilteredPromptIds: (): readonly string[] => host.operations.getFilteredPromptIds(),
        renderItems: (): void => host.operations.renderItems(),
        refreshPromptCards: (ids): void => host.operations.refreshPromptCards(ids),
        updateStats: (): void => host.operations.updateStats(),
        toggleClassName: (element, className, force): void => host.owners.pageDom.toggleClass(element, className, force),
        updateAttribute: (element, name, value): void => host.owners.pageDom.updateAttribute(element, name, value),
        updateText: (element, text): void => host.owners.pageDom.updateText(element, text),
        addClassName: (element, className): void => host.owners.pageDom.addClass(element, className),
        removeClassName: (element, className): void => host.owners.pageDom.removeClass(element, className),
        setElementVisibility: (element, visible): void => setElementVisibility(element, visible)
    });
};

export { createPromptsSelectionManager };
