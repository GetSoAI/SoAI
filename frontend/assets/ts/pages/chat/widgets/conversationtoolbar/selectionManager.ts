/* SoAI - Chat page selection manager [frontend/assets/ts/pages/chat/widgets/conversationtoolbar/selectionManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { syncSelectionActionVisibility, syncSelectionToolbarVisibility } from '@core/selection/toolbarVisibility.ts';
import { getBusyDisabledToken } from '@core/ui/controls/busyDisabledState.ts';
import type { SelectionState } from '@core/selection/state.ts';
import type { ConversationToolbarUiRefs } from '@pages/chat/widgets/conversationtoolbar/types.ts';

interface ConversationSelectionDependencies {
    renderConversationList(): Promise<void>;
}

class ConversationSelectionManager {
    #dependencies: ConversationSelectionDependencies;
    #ui: ConversationToolbarUiRefs | null = null;
    readonly #selection: SelectionState;

    constructor(dependencies: ConversationSelectionDependencies, selection: SelectionState) {
        this.#dependencies = dependencies;
        this.#selection = selection;
    }

    bindUi(refs: ConversationToolbarUiRefs): void {
        this.#ui = refs;
    }

    isActive(): boolean {
        return this.#selection.isActive();
    }

    has(conversationId: string): boolean {
        return this.#selection.has(conversationId);
    }

    list(): readonly string[] {
        return this.#selection.list();
    }

    size(): number {
        return this.#selection.size();
    }

    clear(): void {
        this.#selection.clear();
    }

    activate(): void {
        this.#setSelectionMode(true);
    }

    deactivate(): void {
        this.#selection.clear();
        this.#setSelectionMode(false);
    }

    toggleConversation(conversationId: string): void {
        this.#selection.toggle(conversationId);
        this.#refreshUi();
        this.#scheduleRender();
    }

    removeIds(ids: readonly string[]): void {
        this.#selection.removeMany(ids);
        this.#refreshUi();
    }

    #setSelectionMode(active: boolean): void {
        const ui = this.#requireUi();
        this.#selection.setActive(active);
        syncSelectionToolbarVisibility(
            {
                modeTarget: ui.conversationsList,
                toggleButton: ui.selectButton,
                batchActionsContainer: ui.batchActionsContainer,
                totalElements: [ui.totalConversationsLabel, ui.totalConversationsIcon],
                selectedElements: [ui.selectedCountLabel]
            },
            active
        );
        syncSelectionActionVisibility(ui.openArchivedButton, !active);
        this.#refreshUi();
        this.#scheduleRender();
    }

    #scheduleRender(): void {
        this.#dependencies.renderConversationList().catch((error): void => {
            const runtimeError = ensureError(error);
            errorHandler.warn('ConversationSelectionManager', 'Failed to render conversation list after selection change', runtimeError);
        });
    }

    #refreshUi(): void {
        const ui = this.#ui;
        if (!ui) {
            return;
        }
        const count = this.#selection.size();
        const hasSelection = count > 0;
        ui.selectedCountLabel.textContent = i18n.t('chat.toolbar.selectedCount', { count });
        this.#syncBatchActionButton(ui.batchArchiveButton, hasSelection);
        this.#syncBatchActionButton(ui.batchDeleteButton, hasSelection);
        this.#syncBatchActionButton(ui.batchCloneButton, hasSelection);
    }

    #syncBatchActionButton(button: HTMLButtonElement, hasSelection: boolean): void {
        const isLoading = getBusyDisabledToken(button) !== null;
        button.disabled = isLoading || !hasSelection;
        syncSelectionActionVisibility(button, isLoading || hasSelection);
    }

    #requireUi(): ConversationToolbarUiRefs {
        if (!this.#ui) {
            throw new Error('ConversationSelectionManager UI is not bound');
        }
        return this.#ui;
    }
}

export { ConversationSelectionManager };
export type { ConversationSelectionDependencies };
