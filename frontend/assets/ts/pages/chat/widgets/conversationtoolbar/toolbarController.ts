/* SoAI - Chat page toolbar controller [frontend/assets/ts/pages/chat/widgets/conversationtoolbar/toolbarController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { Conversation } from '@features/chat/public.ts';
import type { ConversationSelectionManager } from '@pages/chat/widgets/conversationtoolbar/selectionManager.ts';
import type { ConversationToolbarUiRefs } from '@pages/chat/widgets/conversationtoolbar/types.ts';

interface ToolbarControllerDependencies {
    getConversations(): ReadonlyMap<string, Conversation>;
    getIconHtml(name: IconName, options?: IconOptions): TrustedHtml;
}

class ConversationToolbarController {
    #dependencies: ToolbarControllerDependencies;
    #selection: ConversationSelectionManager;
    #expanded: boolean = false;
    #ui: ConversationToolbarUiRefs | null = null;
    #outsideClickAbort: AbortController | null = null;

    constructor(dependencies: ToolbarControllerDependencies, selection: ConversationSelectionManager) {
        this.#dependencies = dependencies;
        this.#selection = selection;
    }

    bindUi(refs: ConversationToolbarUiRefs): void {
        this.#disposeOutsideClick();
        this.#ui = refs;
        this.#selection.bindUi(refs);
        this.#injectIcons(refs);
        this.#syncExpansionUi();
    }

    dispose(): void {
        this.#disposeOutsideClick();
    }

    get selection(): ConversationSelectionManager {
        return this.#selection;
    }

    isExpanded(): boolean {
        return this.#expanded;
    }

    toggleExpanded(): void {
        if (this.#expanded) {
            this.#collapse();
        } else {
            this.#expand();
        }
    }

    collapse(): void {
        if (this.#expanded) {
            this.#collapse();
        }
    }

    enterSelectMode(): void {
        if (this.#selection.isActive()) {
            return;
        }
        if (!this.#expanded) {
            this.#expand();
        }
        this.#selection.activate();
    }

    exitSelectMode(): void {
        if (!this.#selection.isActive()) {
            return;
        }
        this.#selection.deactivate();
    }

    isSelectionActive(): boolean {
        return this.#selection.isActive();
    }

    isConversationSelected(conversationId: string): boolean {
        return this.#selection.has(conversationId);
    }

    handleConversationClick(conversationId: string): void {
        this.#selection.toggleConversation(conversationId);
    }

    updateMetrics(): void {
        const ui = this.#ui;
        if (!ui) {
            return;
        }
        let totalConversations = 0;
        for (const conversation of this.#dependencies.getConversations().values()) {
            if (conversation.isArchived !== true) {
                totalConversations += 1;
            }
        }
        ui.totalConversationsLabel.textContent = i18n.t('chat.toolbar.totalConversations', { count: totalConversations });
    }

    #expand(): void {
        this.#expanded = true;
        this.#syncExpansionUi();
        this.#bindOutsideClick();
    }

    #collapse(): void {
        if (this.#selection.isActive()) {
            this.#selection.deactivate();
        }
        this.#expanded = false;
        this.#syncExpansionUi();
        this.#disposeOutsideClick();
    }

    #bindOutsideClick(): void {
        this.#disposeOutsideClick();
        const abortController = new AbortController();
        const { signal } = abortController;
        const handler = (event: Event): void => {
            if (this.#selection.isActive()) {
                return;
            }
            const ui = this.#ui;
            if (!ui) {
                return;
            }
            const target = event.target instanceof Node ? event.target : null;
            if (!target) {
                return;
            }
            if (ui.toolbarContainer.contains(target)) {
                return;
            }
            if (ui.conversationsList.contains(target)) {
                return;
            }
            this.#collapse();
        };
        this.#requireUi().toolbarContainer.ownerDocument.addEventListener('click', handler, { signal });
        this.#outsideClickAbort = abortController;
    }

    #disposeOutsideClick(): void {
        this.#outsideClickAbort?.abort();
        this.#outsideClickAbort = null;
    }

    #injectIcons(refs: ConversationToolbarUiRefs): void {
        this.#setChevronIcons(refs);
        this.#setIcon(refs.openArchivedButton, 'archive');
        this.#setIcon(refs.selectButton, 'select');
        this.#setIcon(refs.batchArchiveButton, 'archive');
        this.#setIcon(refs.batchCloneButton, 'copy');
        this.#setIcon(refs.batchDeleteButton, 'delete');
        this.#setIcon(refs.exitSelectButton, 'close');
    }

    #syncExpansionUi(): void {
        const ui = this.#requireUi();
        ui.toolbarContainer.classList.toggle('is-expanded', this.#expanded);
        ui.toolbarContainer.classList.toggle('is-collapsed', !this.#expanded);
        ui.collapsedChevronToggle.setAttribute('aria-expanded', String(this.#expanded));
        ui.expandedChevronToggle.setAttribute('aria-expanded', String(this.#expanded));
        if (this.#expanded) {
            ui.toolbarContainer.removeAttribute('data-action');
        } else {
            ui.toolbarContainer.setAttribute('data-action', 'chat:toggle-toolbar');
        }
        ui.collapsedLayer.removeAttribute('data-action');
        ui.expandedLayer.removeAttribute('data-action');
        this.#setChevronIcons(ui);
    }

    #setChevronIcons(refs: ConversationToolbarUiRefs): void {
        this.#setIcon(refs.collapsedChevronToggle, 'chevron-up');
        this.#setIcon(refs.expandedChevronToggle, 'chevron-down');
    }

    #setIcon(target: HTMLElement, name: IconName): void {
        const iconSmall: IconOptions = { size: 14, strokeWidth: 1.5 };
        dom.setHTML(target, this.#dependencies.getIconHtml(name, iconSmall), { escape: false });
    }

    #requireUi(): ConversationToolbarUiRefs {
        if (!this.#ui) {
            throw new Error('ConversationToolbarController UI is not bound');
        }
        return this.#ui;
    }
}

export { ConversationToolbarController };
export type { ToolbarControllerDependencies };
