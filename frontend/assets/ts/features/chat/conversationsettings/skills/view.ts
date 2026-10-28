/* SoAI - Incremental skill settings collection presentation [frontend/assets/ts/features/chat/conversationsettings/skills/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { checkerboardService, dom, narrowInput, narrowHTMLElement, narrowButton } from '@core/dom/dom.ts';
import { insertWithPresence, removeWithPresence } from '@core/animations/presence/public.ts';
import { setFieldSurfaceInvalid, setFieldSurfaceModified } from '@core/forms/fieldSurface.ts';
import { RichTextRenderer } from '@core/richtextrenderer/service.ts';
import { createSanitizerApi } from '@core/pagecontext/sanitizer/service.ts';
import { securityApi, toTrustedHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { createToggleSwitch, updateToggleLabel } from '@core/toggleSwitch.ts';
import { createSearchFieldActions } from '@core/ui/searchField.ts';
import { setAriaBusy } from '@core/ui/controls/ariaBusy.ts';
import { createCollectionNoticeAction, renderCollectionEmptyState, renderCollectionNotice, type CollectionNotice } from '@core/ui/collectionFeedback.ts';
import { createSearchTextIndex, matchesSearchFilterQuery } from '@core/search/searchQuery.ts';
import { createIconSlot } from '@core/ui/icons/view.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { setControlDisabledState } from '@core/ui/controls/disabledState.ts';
import type { SkillDetails, SkillLibrary, SkillSummary } from '@core/api/contracts/webuiSkillContractTypes.ts';
import type { SkillSelectionDraft } from '@features/chat/conversationsettings/skills/selectionDraft.ts';
import type { ConversationSettingsHost } from '@features/chat/conversationsettings/conversationSettingsHost.ts';

interface SkillRenderOptions {
    editable: boolean;
    fresh: boolean;
    busy: boolean;
    retryImport: boolean;
    loading?: boolean;
}

interface SkillRow {
    root: HTMLElement;
    toggle: HTMLInputElement;
    name: HTMLElement;
    description: HTMLElement;
    availability: HTMLElement;
}

class SkillSettingsView {
    readonly root: HTMLElement;
    readonly search: HTMLInputElement;
    readonly upload: HTMLInputElement;
    readonly #status: HTMLElement;
    readonly #empty: HTMLElement;
    readonly #list: HTMLElement;
    readonly #details: HTMLElement;
    readonly #renderer: RichTextRenderer;
    readonly #icons: ConversationSettingsHost['view']['getIconSync'];
    readonly #rows = new Map<string, SkillRow>();

    constructor(root: HTMLElement, host: Pick<ConversationSettingsHost['view'], 'getIconSync'>) {
        this.root = root;
        this.#icons = host.getIconSync;
        this.#renderer = new RichTextRenderer({ sanitizer: { ...createSanitizerApi(securityApi), image: () => null }, translateFootnoteBackRef: () => i18n.t('richText.footnotes.backToReference'), isCodeRecognitionEnabled: () => false });
        const controls = dom.resolve('[data-skills-controls]', root);
        const status = dom.resolve('[data-skills-status]', root);
        const empty = dom.resolve('[data-skills-empty]', root);
        const list = dom.resolve('[data-skills-list]', root);
        const details = dom.resolve('[data-skills-details]', root);
        if (!controls || !status || !empty || !list || !details) throw new Error('Skill settings require their modal controls.');
        this.#status = narrowHTMLElement(status, 'Skills status');
        this.#empty = narrowHTMLElement(empty, 'Skills empty state');
        this.#list = narrowHTMLElement(list, 'Skills list');
        this.#details = narrowHTMLElement(details, 'Skills details');
        const searchSurface = dom.create('div', { className: 'searchbar-container searchbar-container--collection' });
        this.search = narrowInput(dom.create('input', { type: 'search', className: 'searchbar-input', autocomplete: 'off', spellcheck: 'false', placeholder: i18n.t('chat.configuration.skills.search'), 'aria-label': i18n.t('chat.configuration.skills.search'), 'data-action': 'skills-search' }), 'Skills search');
        searchSurface.append(this.search, ...createSearchFieldActions(root.ownerDocument));
        this.upload = narrowInput(dom.create('input', { type: 'file', accept: '.md,.zip', className: 'u-hidden', 'data-action': 'skills-upload', 'aria-label': i18n.t('chat.configuration.skills.add') }), 'Skills upload');
        const add = dom.create('button', { type: 'button', className: 'ui-button ui-variant-accent', 'data-action': 'skills-add' });
        add.textContent = i18n.t('chat.configuration.skills.add');
        controls.replaceChildren(searchSurface, add, this.upload);
        this.#list.replaceChildren();
        this.#clearDetails();
    }

    render(library: SkillLibrary | null, draft: SkillSelectionDraft, options: SkillRenderOptions): void {
        this.root.dataset['chatLibraryLoading'] = String(options.loading === true && library === null);
        setAriaBusy(this.root, options.busy || options.loading === true);
        if (options.loading) {
            for (const row of this.#rows.values()) setControlDisabledState(row.toggle, true);
            return;
        }
        const filter = this.search.value;
        let visibleCount = 0;
        const installed = new Set(library?.skills.map((skill) => skill.skillId) ?? []);
        for (const [identity, row] of this.#rows) {
            if (installed.has(identity)) continue;
            if (row.root.contains(dom.getDocument().activeElement)) this.search.focus();
            removeWithPresence(row.root);
            this.#rows.delete(identity);
        }
        for (const skill of library?.skills ?? []) {
            let row = this.#rows.get(skill.skillId);
            if (!row) {
                row = this.#createRow(skill);
                this.#rows.set(skill.skillId, row);
                insertWithPresence(this.#list, row.root);
            }
            row.name.textContent = skill.name;
            row.description.textContent = skill.description;
            row.availability.textContent = skill.disableModelInvocation ? (skill.userInvocable ? i18n.t('chat.configuration.skills.explicit') : i18n.t('chat.configuration.skills.disabledReason')) : skill.userInvocable ? i18n.t('chat.configuration.skills.automatic') : i18n.t('chat.configuration.skills.automaticOnly');
            row.toggle.checked = draft.selected.includes(skill.skillId);
            updateToggleLabel(row.toggle);
            setControlDisabledState(row.toggle, !options.editable || !options.fresh || options.busy || (skill.disableModelInvocation && !skill.userInvocable));
            setFieldSurfaceModified(row.root, row.toggle.checked !== (draft.baseline?.skillIds.includes(skill.skillId) ?? false));
            setFieldSurfaceInvalid(row.root, draft.dirty && !draft.valid && row.toggle.checked);
            const visible = matchesSearchFilterQuery(createSearchTextIndex([skill.name, skill.description]), filter);
            row.root.classList.toggle('u-hidden', !visible);
            if (visible) visibleCount += 1;
        }
        if (library) checkerboardService.applyCheckerboard(this.#list, '.chat-skills-row:not(.u-hidden)');
        else this.dispose();
        renderCollectionNotice(this.#status, this.#resolveStatus(draft, options));
        for (const button of dom.resolveAll('button[data-action]', this.root)) {
            const action = button.getAttribute('data-action');
            setControlDisabledState(narrowButton(button, 'Skill action'), options.busy || (action === 'skills-add' && options.retryImport) || (action === 'skills-keep' && (!draft.conflicted || !options.fresh)));
        }
        this.#list.classList.toggle('u-hidden', visibleCount === 0);
        const emptyLibrary = library?.skills.length === 0;
        renderCollectionEmptyState(
            this.#empty,
            library !== null && visibleCount === 0
                ? {
                      icon: emptyLibrary ? 'skills' : 'search',
                      title: emptyLibrary ? i18n.t('chat.configuration.skills.emptyTitle') : i18n.t('chat.configuration.skills.noMatchesTitle'),
                      message: emptyLibrary ? i18n.t('chat.configuration.skills.empty') : i18n.t('header.search.noResults', { query: filter })
                  }
                : null
        );
    }

    dispose(): void {
        checkerboardService.disconnect(checkerboardService.getContainerId(this.#list));
    }

    showDetails(details: SkillDetails): void {
        const header = dom.create('div', { className: 'chat-config-field-header' });
        const heading = dom.create('h3', { textContent: details.name, dir: 'auto' });
        const close = dom.create('button', { type: 'button', className: 'ui-round-button ui-round-button--inline ui-round-button--modal-close', 'data-action': 'skills-close-details', 'aria-label': i18n.t('common.close') });
        setTooltipText(close, i18n.t('common.close'));
        close.append(createIconSlot(this.root.ownerDocument, this.#icons('close')));
        header.append(heading, close);
        const source = dom.create('div', { className: 'chat-skills-instructions' });
        dom.setHTML(source, toTrustedHtml(this.#renderer.render(details.source)));
        const resources = dom.create('ul');
        for (const resource of details.resources) {
            const item = dom.create('li');
            item.append(resource.isDirectory ? dom.create('span', { textContent: `${resource.path}/` }) : dom.create('button', { type: 'button', className: 'ui-button', textContent: resource.path, 'data-action': 'skills-download', 'data-skill-id': details.skillId, 'data-skill-path': resource.path, 'aria-label': `${i18n.t('common.download')}: ${resource.path}` }));
            resources.append(item);
        }
        this.#details.replaceChildren(header, dom.create('p', { textContent: details.description }), source, resources);
        if (details.compatibility) this.#details.append(dom.create('p', { textContent: details.compatibility }));
        this.#details.classList.remove('u-hidden');
    }

    clearDetails(): void {
        this.#clearDetails();
    }

    #resolveStatus(draft: SkillSelectionDraft, options: SkillRenderOptions): CollectionNotice | null {
        const documentValue = this.root.ownerDocument;
        const reload = (): HTMLButtonElement => createCollectionNoticeAction(documentValue, 'skills-reload', i18n.t('common.refresh'));
        if (options.retryImport && !options.busy) return { tone: 'warning', title: i18n.t('chat.configuration.skills.status.importTitle'), detail: i18n.t('chat.configuration.skills.importUncertain'), actions: [reload()] };
        if (draft.conflicted) return { tone: 'warning', title: i18n.t('chat.configuration.skills.status.conflictTitle'), detail: i18n.t('chat.configuration.skills.conflict'), actions: [reload(), createCollectionNoticeAction(documentValue, 'skills-keep', i18n.t('chat.configuration.skills.keepDraft'))] };
        if (!options.fresh) return { tone: 'warning', title: i18n.t('chat.configuration.skills.status.staleTitle'), detail: i18n.t('chat.configuration.skills.stale'), actions: [reload()] };
        if (!options.editable) return { tone: 'info', title: i18n.t('chat.configuration.skills.status.unavailableTitle'), detail: i18n.t('chat.configuration.skills.unavailable'), actions: [] };
        if (draft.dirty && !draft.valid) return { tone: 'warning', title: i18n.t('chat.configuration.skills.status.invalidTitle'), detail: i18n.t('chat.configuration.skills.invalidSelection'), actions: [reload()] };
        return null;
    }

    #clearDetails(): void {
        this.#details.classList.add('u-hidden');
        this.#details.replaceChildren();
    }

    #createRow(skill: SkillSummary): SkillRow {
        const root = dom.create('div', { className: 'collection-list-item chat-skills-row glass-surface-interactive setting-change-surface', role: 'listitem', 'data-skill-id': skill.skillId });
        const toggleSurface = createToggleSwitch({ id: `skill-toggle-${skill.skillId}`, checked: false, labels: { trueLabel: i18n.t('common.enabled'), falseLabel: i18n.t('common.disabled') }, showLabel: false, ariaLabel: skill.name, inputDataset: { action: 'skills-toggle', skillId: skill.skillId } });
        const input = dom.resolve('input', toggleSurface);
        if (!input) throw new Error('Skill toggle requires its checkbox.');
        const toggle = narrowInput(input, 'Skill checkbox');
        const summary = dom.create('div', { className: 'collection-list-item-main chat-skills-summary' });
        const name = dom.create('label', { for: toggle.id, className: 'collection-list-item-title', dir: 'auto' });
        const description = dom.create('p', { className: 'collection-list-item-meta', dir: 'auto' });
        const availability = dom.create('span', { className: 'chat-configuration-hint' });
        const metadata = dom.create('div', { className: 'chat-skills-metadata' });
        metadata.append(dom.create('code', { textContent: `$${skill.name}`, dir: 'ltr' }), availability);
        summary.append(name, description, metadata);
        const actions = dom.create('div', { className: 'ui-collection-list__actions chat-skills-actions' });
        const details = dom.create('button', { type: 'button', className: 'ui-round-button ui-round-button--inline ui-round-button--settings', 'data-action': 'skills-details', 'data-skill-id': skill.skillId, 'aria-label': i18n.t('common.view') });
        const remove = dom.create('button', { type: 'button', className: 'ui-round-button ui-round-button--inline ui-round-button--delete', 'data-action': 'skills-remove', 'data-skill-id': skill.skillId, 'aria-label': i18n.t('common.delete') });
        setTooltipText(details, i18n.t('common.view'));
        setTooltipText(remove, i18n.t('common.delete'));
        details.append(createIconSlot(root.ownerDocument, this.#icons('eye-open')));
        remove.append(createIconSlot(root.ownerDocument, this.#icons('close')));
        actions.append(remove, details);
        root.append(summary, toggleSurface, actions);
        return { root, toggle, name, description, availability };
    }
}

export { SkillSettingsView };
