/* SoAI - Conversation find header and local result presentation [frontend/assets/ts/pages/chat/controllers/conversationfind/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isPresenceExiting, prepareEnterWithPresence } from '@core/animations/presence/public.ts';
import { requireRootHTMLElement } from '@core/dom/typedElementResolver.ts';
import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { renderLabelAttributes } from '@core/security/public.ts';
import { createIconSlot } from '@core/ui/icons/view.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { wallClockMs } from '@core/time/clock.ts';
import type { ResourceTracker } from '@core/resourcetracker/service.ts';
import { SearchBar } from '@features/controls/public.ts';
import type { ConversationFindSearchSnapshot } from '@pages/chat/controllers/conversationfind/contracts.ts';
import type { ConversationFindRevealStatus } from '@pages/chat/controllers/conversationfind/ConversationFindRevealController.ts';

const renderConversationFindMarkup = (): string => {
    return `<div class="conversation-find u-hidden" data-presence data-presence-atomic data-presence-visual-only>
        <div class="conversation-find-field"></div>
        <span class="conversation-find-counter" dir="auto"></span>
        <button type="button" class="conversation-find-prev ui-icon-button u-hidden" data-presence data-presence-atomic data-action="chat:find-previous" ${renderLabelAttributes(i18n.t('chat.find.previous'))}></button>
        <button type="button" class="conversation-find-next ui-icon-button u-hidden" data-presence data-presence-atomic data-action="chat:find-next" ${renderLabelAttributes(i18n.t('chat.find.next'))}></button>
        <button type="button" class="conversation-find-close ui-button ui-variant-neutral" data-action="chat:find-close" ${renderLabelAttributes(i18n.t('chat.find.close'))}><span class="conversation-find-close-label">${i18n.t('chat.find.close')}</span></button>
        <div class="conversation-find-status u-hidden" role="status" aria-live="polite"><span class="conversation-find-status-text" dir="auto"></span><button type="button" class="conversation-find-retry ui-button ui-variant-neutral u-hidden" data-presence data-presence-atomic data-action="chat:find-retry" ${renderLabelAttributes(i18n.t('chat.find.retry'))}>${i18n.t('chat.find.retry')}</button></div>
    </div>`;
};

const renderConversationFindSpatialMarkup = (): string => `<button type="button" class="conversation-find-spatial conversation-find-spatial--before ui-button ui-variant-neutral u-hidden" data-action="chat:find-previous" ${renderLabelAttributes(i18n.t('chat.find.previous'))}><span class="conversation-find-spatial-count"></span></button><button type="button" class="conversation-find-spatial conversation-find-spatial--after ui-button ui-variant-neutral u-hidden" data-action="chat:find-next" ${renderLabelAttributes(i18n.t('chat.find.next'))}><span class="conversation-find-spatial-count"></span></button>`;

class ConversationFindView {
    readonly wrapper: HTMLElement;
    readonly searchBar: SearchBar;
    readonly input: HTMLInputElement;
    readonly #counter: HTMLElement;
    readonly #previous: HTMLButtonElement;
    readonly #next: HTMLButtonElement;
    readonly #status: HTMLElement;
    readonly #statusText: HTMLElement;
    readonly #retry: HTMLButtonElement;
    readonly #spatial: Element[];
    readonly #openButtons: HTMLElement[];
    readonly #resources: Pick<ResourceTracker, 'setTimeout' | 'clearTimer'>;
    #ageTimer: number | null = null;
    #language = '';

    constructor(root: HTMLElement, onSearch: () => void, onClear: () => void, resources: Pick<ResourceTracker, 'setTimeout' | 'clearTimer'>) {
        this.#resources = resources;
        this.wrapper = requireRootHTMLElement(root, '.conversation-find', 'Conversation find');
        this.#counter = requireRootHTMLElement(root, '.conversation-find-counter', 'Conversation find');
        const previous = requireRootHTMLElement(root, '.conversation-find-prev', 'Conversation find');
        const next = requireRootHTMLElement(root, '.conversation-find-next', 'Conversation find');
        const retry = requireRootHTMLElement(root, '.conversation-find-retry', 'Conversation find');
        if (!(previous instanceof HTMLButtonElement) || !(next instanceof HTMLButtonElement) || !(retry instanceof HTMLButtonElement)) throw new Error('Conversation find requires navigation buttons');
        this.#previous = previous;
        this.#next = next;
        this.#retry = retry;
        previous.append(createIconSlot(root.ownerDocument, getIconSync('chevron-up', { size: 16 })));
        next.append(createIconSlot(root.ownerDocument, getIconSync('chevron-down', { size: 16 })));
        this.#openButtons = dom.resolveAll('.conversation-find-open', root).filter((element): element is HTMLElement => element instanceof HTMLElement);
        requireRootHTMLElement(root, '.conversation-find-close', 'Conversation find Close').append(createIconSlot(root.ownerDocument, getIconSync('close', { size: 16 }), { className: 'ui-icon conversation-find-close-icon' }));
        this.#spatial = dom.resolveAll('.conversation-find-spatial', root);
        for (const button of this.#spatial) button.prepend(createIconSlot(root.ownerDocument, getIconSync(button.classList.contains('conversation-find-spatial--before') ? 'chevron-up' : 'chevron-down', { size: 16 })));
        this.#status = requireRootHTMLElement(root, '.conversation-find-status', 'Conversation find');
        this.#statusText = requireRootHTMLElement(root, '.conversation-find-status-text', 'Conversation find');
        this.searchBar = new SearchBar({ placeholder: i18n.t('chat.find.placeholder'), debounceTime: 1000, alwaysExpanded: true, onSearch, onClear, containerClass: 'conversation-find-search' });
        this.searchBar.initialize(requireRootHTMLElement(root, '.conversation-find-field', 'Conversation find'));
        const input = this.searchBar.getInput();
        if (!input) throw new Error('Conversation find requires a search input');
        this.input = input;
        input.setAttribute('aria-label', i18n.t('chat.find.open'));
        input.setAttribute('autocomplete', 'off');
        input.setAttribute('spellcheck', 'false');
    }

    render(snapshot: ConversationFindSearchSnapshot, reveal: ConversationFindRevealStatus): void {
        if (this.#ageTimer !== null) this.#resources.clearTimer(this.#ageTimer);
        this.#ageTimer = null;
        if (snapshot.open && snapshot.status === 'stale' && snapshot.verifiedAt !== null) {
            const timerId = this.#resources.setTimeout(() => {
                if (this.#ageTimer !== timerId) return;
                this.#ageTimer = null;
                this.render(snapshot, reveal);
            }, 1000);
            this.#ageTimer = timerId;
        }
        const language = this.input.ownerDocument.documentElement.lang;
        if (this.#language !== language) {
            this.#language = language;
            this.searchBar.updateOptions({ placeholder: i18n.t('chat.find.placeholder') });
            this.input.setAttribute('aria-label', i18n.t('chat.find.open'));
            for (const button of this.#openButtons) {
                button.setAttribute('aria-label', i18n.t('chat.find.open'));
                setTooltipText(button, i18n.t('chat.find.open'));
                const label = dom.resolve('.chat-action-label', button);
                if (label) label.textContent = i18n.t('chat.find.open');
            }
            for (const button of [this.#previous, this.#next]) {
                const label = button === this.#previous ? i18n.t('chat.find.previous') : i18n.t('chat.find.next');
                button.setAttribute('aria-label', label);
                setTooltipText(button, label);
            }
            const done = requireRootHTMLElement(this.wrapper, '.conversation-find-close', 'Conversation find Close');
            done.setAttribute('aria-label', i18n.t('chat.find.close'));
            setTooltipText(done, i18n.t('chat.find.close'));
            requireRootHTMLElement(done, '.conversation-find-close-label', 'Conversation find Close label').textContent = i18n.t('chat.find.close');
            this.#retry.textContent = i18n.t('chat.find.retry');
        }
        const total = snapshot.index.totalOccurrences;
        const ordinal = snapshot.target === null ? null : snapshot.index.ordinalOf(snapshot.target);
        const counter = !snapshot.query || snapshot.status === 'too-long' ? '' : total > 0 ? i18n.t('chat.find.count', { current: ordinal === null ? 0 : ordinal + 1, total }) : snapshot.status === 'ready' ? i18n.t('chat.find.none') : '';
        if (this.#counter.textContent !== counter) this.#counter.textContent = counter;
        for (const button of [this.#previous, this.#next]) {
            button.classList.toggle('u-hidden', snapshot.query.length === 0);
            if (snapshot.query && isPresenceExiting(button)) prepareEnterWithPresence(button, true)();
        }
        this.#previous.disabled = total === 0 || ordinal === 0;
        this.#next.disabled = total === 0 || ordinal === total - 1;
        for (const button of this.#spatial) {
            const before = button.classList.contains('conversation-find-spatial--before');
            const count = ordinal === null ? 0 : before ? ordinal : total - ordinal - 1;
            button.classList.toggle('u-hidden', !snapshot.open || count === 0);
            button.setAttribute('aria-label', before ? i18n.t('chat.find.before', { count }) : i18n.t('chat.find.after', { count }));
            const value = dom.resolve('.conversation-find-spatial-count', button);
            if (value && value.textContent !== String(count)) value.textContent = String(count);
        }
        let status = '';
        if (snapshot.status === 'too-long') status = i18n.t('chat.find.tooLong');
        else if (snapshot.status === 'stale') status = snapshot.verifiedAt === null ? i18n.t('chat.find.disconnected') : i18n.t('chat.find.stale', { seconds: Math.max(0, Math.floor((wallClockMs() - snapshot.verifiedAt) / 1000)) });
        else if (snapshot.status === 'incomplete') status = i18n.t('chat.find.incomplete');
        else if (snapshot.status === 'error') status = i18n.t('chat.find.error');
        else if (snapshot.status === 'updating') status = i18n.t('chat.find.updating');
        else if (reveal === 'editing') status = i18n.t('chat.find.editing');
        else if (reveal === 'missing') status = i18n.t('chat.find.missing');
        else if (reveal === 'timeout') status = i18n.t('chat.find.timeout');
        else if (reveal === 'error') status = i18n.t('chat.find.error');
        else if (snapshot.needsRefill) status = i18n.t('chat.find.incomplete');
        else if (snapshot.truncated) status = i18n.t('chat.find.limited');
        if (this.#statusText.textContent !== status) this.#statusText.textContent = status;
        this.#status.classList.toggle('u-hidden', status.length === 0);
        this.#retry.classList.toggle('u-hidden', !(snapshot.needsRefill || ['incomplete', 'error'].includes(snapshot.status) || snapshot.failure === 'conflict' || (reveal !== null && reveal !== 'loading' && reveal !== 'editing')));
        this.searchBar.setLoading(snapshot.open && (snapshot.showSearching || reveal === 'loading'));
        this.wrapper.setAttribute('aria-busy', snapshot.status === 'scanning' || snapshot.status === 'updating' || reveal === 'loading' ? 'true' : 'false');
        this.input.setAttribute('aria-invalid', snapshot.status === 'too-long' ? 'true' : 'false');
    }

    dispose(): void {
        if (this.#ageTimer !== null) this.#resources.clearTimer(this.#ageTimer);
        this.#ageTimer = null;
        this.searchBar.destroy();
    }
}

export { ConversationFindView, renderConversationFindMarkup, renderConversationFindSpatialMarkup };
