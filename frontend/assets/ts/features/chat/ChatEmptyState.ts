/* SoAI - Chat feature empty state [frontend/assets/ts/features/chat/ChatEmptyState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { dom } from '@core/dom/dom.ts';
import { createOverflowNavButtonMarkup, OverflowNavController } from '@core/ui/controls/OverflowNav.ts';
import { renderDropdownChevron } from '@core/ui/dropdown/chevron.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { CHAT_ICON_SIZE_LG, CHAT_ICON_SIZE_SM } from '@features/chat/chatConstants.ts';
import { resolveAuthorityLockedControlLabel, type ConversationAuthorityLock } from '@core/chat/conversationAuthorityLock.ts';
import type { AgentMode } from '@core/chat/agentMode.ts';

interface ChatPageSuggestionConfig {
    icon: IconName;
    getTitle: () => string;
    getText: () => string;
}

interface ChatPageEmptyStateDependencies {
    sanitizer: {
        html: (value: string) => string;
        attribute: (value: string) => string;
    };
    getCachedIcon: (name: IconName, options?: IconOptions) => TrustedHtml;
    activeAgentMode: AgentMode;
    authorityLock: ConversationAuthorityLock | null;
    ctrlEnterSendRequired: boolean;
    isMac?: boolean;
}

const SUGGESTION_CONFIGS: readonly ChatPageSuggestionConfig[] = Object.freeze([
    { icon: 'explain', getTitle: () => i18n.t('chat.suggestions.explainTitle'), getText: () => i18n.t('chat.suggestions.explainText') },
    { icon: 'code', getTitle: () => i18n.t('chat.suggestions.codeTitle'), getText: () => i18n.t('chat.suggestions.codeText') },
    { icon: 'edit', getTitle: () => i18n.t('chat.suggestions.writeTitle'), getText: () => i18n.t('chat.suggestions.writeText') },
    { icon: 'mail', getTitle: () => i18n.t('chat.suggestions.emailReplyTitle'), getText: () => i18n.t('chat.suggestions.emailReplyText') },
    { icon: 'keypad', getTitle: () => i18n.t('chat.suggestions.solveTitle'), getText: () => i18n.t('chat.suggestions.solveText') },
    { icon: 'unit-convert', getTitle: () => i18n.t('chat.suggestions.unitConversionTitle'), getText: () => i18n.t('chat.suggestions.unitConversionText') },
    { icon: 'thinking', getTitle: () => i18n.t('chat.suggestions.brainstormTitle'), getText: () => i18n.t('chat.suggestions.brainstormText') },
    { icon: 'metrics', getTitle: () => i18n.t('chat.suggestions.analyzeTitle'), getText: () => i18n.t('chat.suggestions.analyzeText') },
    { icon: 'summarize', getTitle: () => i18n.t('chat.suggestions.summarizeTitle'), getText: () => i18n.t('chat.suggestions.summarizeText') },
    { icon: 'bug', getTitle: () => i18n.t('chat.suggestions.debugTitle'), getText: () => i18n.t('chat.suggestions.debugText') },
    { icon: 'law-scale', getTitle: () => i18n.t('chat.suggestions.compareTitle'), getText: () => i18n.t('chat.suggestions.compareText') },
    { icon: 'lowest-price', getTitle: () => i18n.t('chat.suggestions.lowestPriceTitle'), getText: () => i18n.t('chat.suggestions.lowestPriceText') },
    { icon: 'tasks', getTitle: () => i18n.t('chat.suggestions.planTitle'), getText: () => i18n.t('chat.suggestions.planText') },
    { icon: 'translate', getTitle: () => i18n.t('chat.suggestions.translateTitle'), getText: () => i18n.t('chat.suggestions.translateText') },
    { icon: 'book-open', getTitle: () => i18n.t('chat.suggestions.reviewTitle'), getText: () => i18n.t('chat.suggestions.reviewText') },
    { icon: 'simplify', getTitle: () => i18n.t('chat.suggestions.simplifyTitle'), getText: () => i18n.t('chat.suggestions.simplifyText') },
    { icon: 'sword', getTitle: () => i18n.t('chat.suggestions.roleplayTitle'), getText: () => i18n.t('chat.suggestions.roleplayText') },
    { icon: 'redo', getTitle: () => i18n.t('chat.suggestions.rewriteTitle'), getText: () => i18n.t('chat.suggestions.rewriteText') },
    { icon: 'news', getTitle: () => i18n.t('chat.suggestions.newsTitle'), getText: () => i18n.t('chat.suggestions.newsText') },
    { icon: 'search', getTitle: () => i18n.t('chat.suggestions.researchTitle'), getText: () => i18n.t('chat.suggestions.researchText') },
    { icon: 'glasses', getTitle: () => i18n.t('chat.suggestions.proofreadTitle'), getText: () => i18n.t('chat.suggestions.proofreadText') },
    { icon: 'outline', getTitle: () => i18n.t('chat.suggestions.outlineTitle'), getText: () => i18n.t('chat.suggestions.outlineText') },
    { icon: 'question', getTitle: () => i18n.t('chat.suggestions.quizTitle'), getText: () => i18n.t('chat.suggestions.quizText') },
    { icon: 'external-link', getTitle: () => i18n.t('chat.suggestions.expandTitle'), getText: () => i18n.t('chat.suggestions.expandText') },
    { icon: 'thumbs-down', getTitle: () => i18n.t('chat.suggestions.critiqueTitle'), getText: () => i18n.t('chat.suggestions.critiqueText') }
]);

class ChatPageEmptyState {
    #overflowNavController: OverflowNavController | null = null;
    #suggestionOrder: ChatPageSuggestionConfig[] | null = null;

    buildMarkup(dependencies: ChatPageEmptyStateDependencies): TrustedHtml {
        const { sanitizer: stringValue, getCachedIcon, activeAgentMode, authorityLock, ctrlEnterSendRequired, isMac } = dependencies;
        const leftLabel = i18n.t('tabs.scrollLeft');
        const rightLabel = i18n.t('tabs.scrollRight');

        const leftButtonHtml = createOverflowNavButtonMarkup({
            direction: 'left',
            className: 'chat-page-suggestion-nav chat-page-suggestion-nav--left ui-icon-button',
            label: leftLabel,
            iconName: 'chevron-left',
            iconOptions: { size: 20, strokeWidth: 1.5 }
        });

        const rightButtonHtml = createOverflowNavButtonMarkup({
            direction: 'right',
            className: 'chat-page-suggestion-nav chat-page-suggestion-nav--right ui-icon-button',
            label: rightLabel,
            iconName: 'chevron-right',
            iconOptions: { size: 20, strokeWidth: 1.5 }
        });

        const suggestionConfigs = this.#getSuggestionOrder();
        const cards = suggestionConfigs
            .map((config) => {
                const text = config.getText();
                const title = config.getTitle();
                const iconHtml = getCachedIcon(config.icon, CHAT_ICON_SIZE_LG).html;
                const titleHtml = stringValue.html(title);
                const textHtml = stringValue.html(text);
                const textAttribute = stringValue.attribute(text);
                const titleAttribute = stringValue.attribute(title);

                return `<button type="button" class="chat-page-suggestion-card" data-action="chat:suggestion" data-text="${textAttribute}" aria-label="${titleAttribute}: ${textAttribute}" data-tooltip="${titleAttribute}: ${textAttribute}">
                <span class="chat-page-suggestion-card-icon" aria-hidden="true">${iconHtml}</span>
                <span class="chat-page-suggestion-card-title">${titleHtml}</span>
                <span class="chat-page-suggestion-card-text" data-tooltip="${textAttribute}">${textHtml}</span>
            </button>`;
            })
            .join('');

        const headingText = stringValue.html(i18n.t('chat.empty.title'));
        const subtitleText = stringValue.html(i18n.t('chat.empty.description'));

        const modelIconHtml = getCachedIcon('model-default', CHAT_ICON_SIZE_SM).html;
        const modelLabelText = stringValue.html(i18n.t('chat.empty.modelLabel'));
        const selectModelText = stringValue.html(i18n.t('chat.sidebar.selectModel'));
        const modelIndicatorHtml = `<div class="chat-page-model-indicator">
            <span class="chat-page-model-indicator-icon">${modelIconHtml}</span>
            <span class="chat-page-model-indicator-label">${modelLabelText}</span>
            <div class="model-selector chat-page-model-indicator-select page-header-filter-select" data-chat-model-control="true" data-scope="empty-state" aria-label="${selectModelText}" data-tooltip="${selectModelText}"></div>
        </div>`;

        const modeIconHtml = getCachedIcon('chat', CHAT_ICON_SIZE_SM).html;
        const modeChevronHtml = renderDropdownChevron(getCachedIcon, 'chat-page-mode-indicator-chevron');
        const modeLabel = i18n.t('chat.empty.modeLabel');
        const modeLabelText = stringValue.html(modeLabel);
        const modeIndicatorLockAttributes = authorityLock === null ? '' : ` data-settings-authority-lock="${stringValue.attribute(authorityLock.authorityType)}" data-tooltip="${stringValue.attribute(authorityLock.reason)}"`;
        const modeSelectLabelText = authorityLock === null ? modeLabelText : stringValue.attribute(resolveAuthorityLockedControlLabel(authorityLock, modeLabel));
        const modeSelectLockAttributes = authorityLock === null ? '' : ' disabled aria-disabled="true"';
        const modeIndicatorHtml = `<div class="chat-page-mode-indicator"${modeIndicatorLockAttributes}>
            <span class="chat-page-mode-indicator-icon">${modeIconHtml}</span>
            <span class="chat-page-mode-indicator-label">${modeLabelText}</span>
            <select class="chat-page-mode-indicator-select page-header-filter-select" data-agent-mode="${activeAgentMode}" aria-label="${modeSelectLabelText}"${modeSelectLockAttributes}>
                <option value="chat"${activeAgentMode === 'chat' ? ' selected' : ''}>${stringValue.html(i18n.t('chat.agent.mode.chat'))}</option>
                <option value="plan"${activeAgentMode === 'plan' ? ' selected' : ''}>${stringValue.html(i18n.t('chat.agent.mode.plan'))}</option>
                <option value="execute"${activeAgentMode === 'execute' ? ' selected' : ''}>${stringValue.html(i18n.t('chat.agent.mode.execute'))}</option>
            </select>
            ${modeChevronHtml}
        </div>`;

        const indicatorRowHtml = `<div class="chat-page-indicator-row">
            ${modelIndicatorHtml}
            ${modeIndicatorHtml}
        </div>`;

        const modificationKey = isMac ? '⌘' : 'Ctrl';
        const sendModifierHtml = ctrlEnterSendRequired ? `<kbd class="chat-page-kbd">${modificationKey}</kbd><span class="chat-page-kbd-separator">+</span>` : '';
        const shortcutsHtml = `<div class="chat-page-shortcuts glass-surface">
            <div class="chat-page-shortcut">
                ${sendModifierHtml}
                <kbd class="chat-page-kbd">Enter</kbd>
                <span class="chat-page-shortcut-label">${stringValue.html(i18n.t('chat.empty.shortcuts.send'))}</span>
            </div>
            <div class="chat-page-shortcut">
                <kbd class="chat-page-kbd">Shift</kbd>
                <span class="chat-page-kbd-separator">+</span>
                <kbd class="chat-page-kbd">Enter</kbd>
                <span class="chat-page-shortcut-label">${stringValue.html(i18n.t('chat.empty.shortcuts.newline'))}</span>
            </div>
            <div class="chat-page-shortcut">
                <kbd class="chat-page-kbd">Tab</kbd>
                <span class="chat-page-shortcut-label">${stringValue.html(i18n.t('chat.empty.shortcuts.queuePrompt'))}</span>
            </div>
            <div class="chat-page-shortcut">
                <kbd class="chat-page-kbd">Shift</kbd>
                <span class="chat-page-kbd-separator">+</span>
                <kbd class="chat-page-kbd">Tab</kbd>
                <span class="chat-page-shortcut-label">${stringValue.html(i18n.t('chat.empty.shortcuts.switchMode'))}</span>
            </div>
            <div class="chat-page-shortcut">
                <kbd class="chat-page-kbd">Esc</kbd>
                <span class="chat-page-shortcut-label">${stringValue.html(i18n.t('chat.empty.shortcuts.stop'))}</span>
            </div>
        </div>`;

        const inputHintIcon = getCachedIcon('chevron-down', { size: 50, strokeWidth: 1 }).html;
        const inputHintHtml = `<div class="chat-page-input-hint" aria-hidden="true">${inputHintIcon}</div>`;

        const emptyStateIcon = getCachedIcon('chat', {
            size: 80,
            strokeWidth: 1.5,
            attributes: { 'aria-hidden': 'true', focusable: 'false' }
        }).html;
        const emptyStateIconHtml = `<div class="chat-page-empty-state-icon" aria-hidden="true">${emptyStateIcon}</div>`;

        return toTrustedUiHtml(`<div class="chat-page-empty-state">
            <div class="chat-page-empty-state-header">
                <div class="chat-page-empty-state-title-row">
                    ${emptyStateIconHtml}
                    <h2 class="chat-page-empty-state-heading">${headingText}</h2>
                </div>
                <p class="chat-page-empty-state-subtitle">${subtitleText}</p>
                ${indicatorRowHtml}
            </div>
            <div class="chat-page-suggestion-row-wrapper">
                ${leftButtonHtml}
                <div class="chat-page-suggestion-row">${cards}</div>
                ${rightButtonHtml}
            </div>
            ${shortcutsHtml}
            ${inputHintHtml}
        </div>`);
    }

    initializeOverflowNav(container: Element, addEventListener: (target: EventTarget, type: string, listener: EventListener, options?: AddEventListenerOptions) => () => void): void {
        this.dispose();

        const rowValue = dom.resolve('.chat-page-suggestion-row', container);
        if (!(rowValue instanceof HTMLElement)) return;
        const row = rowValue;

        const maxScrollLeft = Math.max(row.scrollWidth - row.clientWidth, 0);
        if (maxScrollLeft > 0) {
            const target = Math.round(maxScrollLeft / 2);
            if (typeof row.scrollTo === 'function') {
                row.scrollTo({ left: target, behavior: 'auto' });
            } else {
                row.scrollLeft = target;
            }
        }

        const leftValue = dom.resolve('.chat-page-suggestion-nav--left', container);
        const rightValue = dom.resolve('.chat-page-suggestion-nav--right', container);
        if (!(leftValue instanceof HTMLElement) || !(rightValue instanceof HTMLElement)) return;
        const leftButton = leftValue;
        const rightButton = rightValue;

        this.#overflowNavController = new OverflowNavController(row, leftButton, rightButton);
        this.#overflowNavController.initialize(addEventListener);
    }

    dispose(): void {
        this.#overflowNavController?.dispose();
        this.#overflowNavController = null;
    }

    #getSuggestionOrder(): ChatPageSuggestionConfig[] {
        if (this.#suggestionOrder) {
            return this.#suggestionOrder;
        }
        this.#suggestionOrder = this.#shuffleItems(SUGGESTION_CONFIGS);
        return this.#suggestionOrder;
    }

    #shuffleItems<T>(source: readonly T[]): T[] {
        const items = [...source];
        for (let index = items.length - 1; index > 0; index -= 1) {
            const randomIndex = Math.floor(Math.random() * (index + 1));
            const current = items[index];
            const swap = items[randomIndex];
            if (current === undefined || swap === undefined) {
                continue;
            }
            items[index] = swap;
            items[randomIndex] = current;
        }
        return items;
    }
}

export { ChatPageEmptyState };
export type { ChatPageSuggestionConfig, ChatPageEmptyStateDependencies };
