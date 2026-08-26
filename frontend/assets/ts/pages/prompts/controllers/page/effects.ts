/* SoAI - Prompts page effects [frontend/assets/ts/pages/prompts/controllers/page/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readTrimmedInputValue } from '@core/dom/formValues.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString } from '@core/normalize.ts';
import type { SaveController } from '@core/save/public.ts';
import type { PromptRecord } from '@features/prompts/public.ts';
import { createPromptRecord, updatePromptRecord } from '@pages/prompts/controllers/page/promptRecordManager.ts';
import type { PromptsRuntimeContext } from '@pages/prompts/controllers/page/contracts.ts';

type PromptsPageActionsHost = PromptsRuntimeContext;

const DRAFT_PROMPT_ID_PREFIX = 'prompt-draft:';

const isDraftPromptId = (promptId: string): boolean => promptId.startsWith(DRAFT_PROMPT_ID_PREFIX);

const setupUnsavedChangesGuard = (host: PromptsPageActionsHost): void => {
    host.state.unsavedChangesGuardCleanup?.();
    host.state.unsavedChangesGuardCleanup = host.owners.layout.registerUnsavedChanges({
        hasUnsavedChanges: () => host.operations.hasUnsavedChanges(),
        confirmMessage: i18n.t('prompts.unsavedChanges'),
        guardId: 'prompts-dirty-guard'
    });
};

const handleCardColorSelection = (host: PromptsPageActionsHost, save: SaveController, promptId: string, button: HTMLElement): void => {
    const card = host.owners.pageDom.optional(`.prompt-card[data-prompt-id="${promptId}"], .prompts-list-row[data-prompt-id="${promptId}"]`);
    if (!(card instanceof HTMLElement) || !(button instanceof HTMLElement)) {
        return;
    }
    const current = host.components.colorToolkit.normalize(card.dataset['selectedColor']);
    const candidate = host.components.colorToolkit.normalize(button.dataset['color']);
    host.components.colorToolkit.applyToCard(card, current === candidate ? null : candidate);
    save.notifyChanged();
};

const createDraftPromptCard = (host: PromptsPageActionsHost, save: SaveController): void => {
    if (host.state.draftPromptId) {
        host.state.editingPromptId = host.state.draftPromptId;
        host.operations.reapplyCollection({ shouldRender: true, updateStats: false, updateFilters: false });
        return;
    }
    const createdAtMs = Date.now();
    const draftId = `${DRAFT_PROMPT_ID_PREFIX}${createdAtMs}`;
    host.operations.upsertItem({ id: draftId, name: i18n.t('prompts.unnamedPrompt'), content: '', color: null, createdAtMs, modifiedAtMs: createdAtMs });
    host.state.draftPromptId = draftId;
    host.state.editingPromptId = draftId;
    host.operations.reapplyCollection({ shouldRender: true, updateStats: true, updateFilters: false });
    save.notifyChanged();
};

const discardDraftPromptCard = (host: PromptsPageActionsHost, promptId: string): void => {
    if (host.state.draftPromptId !== promptId) {
        return;
    }
    host.state.draftPromptId = null;
    host.operations.removeItemById(promptId);
};

const startEditing = async (host: PromptsPageActionsHost, save: SaveController, promptId: string): Promise<void> => {
    if (!promptId) {
        return;
    }
    if (host.state.editingPromptId && host.state.editingPromptId !== promptId) {
        host.state.editingPromptId = null;
    }
    host.state.editingPromptId = promptId;
    host.operations.reapplyCollection({ shouldRender: true, updateStats: false, updateFilters: false });
    save.notifyChanged();
};

const cancelEditing = async (host: PromptsPageActionsHost, save: SaveController, promptId: string): Promise<void> => {
    if (!promptId || host.state.editingPromptId !== promptId) {
        return;
    }
    host.state.editingPromptId = null;
    discardDraftPromptCard(host, promptId);
    host.operations.reapplyCollection({ shouldRender: true, updateStats: true, updateFilters: false });
    save.notifyChanged();
};

const saveEditing = async (host: PromptsPageActionsHost, promptId: string): Promise<void> => {
    await host.owners.pageLifecycle.run('prompts:saveEditing', async () => {
        const isDraft = host.state.draftPromptId === promptId;
        const existing = host.operations.findPromptById(promptId);
        if (!existing) {
            host.state.editingPromptId = null;
            host.operations.reapplyCollection({ shouldRender: true, updateStats: true, updateFilters: false });
            return;
        }
        const cardCandidate = host.owners.pageDom.optional(`.prompt-card[data-prompt-id="${promptId}"], .prompts-list-row[data-prompt-id="${promptId}"]`);
        const card = cardCandidate instanceof HTMLElement ? cardCandidate : null;
        if (!card) {
            throw new Error('Prompt edit card is missing');
        }
        const nameCandidate = host.owners.pageDom.optional('input[data-field="name"]', card);
        const contentCandidate = host.owners.pageDom.optional('textarea[data-field="content"]', card);
        if (!(nameCandidate instanceof HTMLInputElement)) {
            throw new TypeError('Prompt edit card requires name input');
        }
        if (!(contentCandidate instanceof HTMLTextAreaElement)) {
            throw new TypeError('Prompt edit card requires content textarea');
        }

        const selectedColor = host.components.colorToolkit.normalize(card.dataset['selectedColor'] ?? null);
        const payload = {
            name: readTrimmedInputValue(nameCandidate),
            content: contentCandidate.value,
            color: selectedColor
        };

        const saved = isDraft ? await host.owners.streaming.runTask('prompts.create', () => createPromptRecord(host, payload, 'PromptsPage.createPrompt'), { displayName: i18n.t('prompts.actions.createPrompt'), rethrow: false }) : await host.owners.streaming.runTask('prompts.update', () => updatePromptRecord(host, promptId, payload, 'PromptsPage.updatePrompt'), { displayName: i18n.t('prompts.actions.save'), rethrow: false });
        if (!saved) {
            return;
        }
        discardDraftPromptCard(host, promptId);
        host.operations.upsertPromptRecord(saved);
        host.state.editingPromptId = null;
        host.operations.reapplyCollection({ shouldRender: true, updateStats: true, updateFilters: false });
        host.owners.feedback.show(i18n.t('prompts.notifications.promptSaved'), 'success');
    });
};

const duplicateSelected = async (host: PromptsPageActionsHost, save: SaveController): Promise<void> => {
    await host.owners.pageLifecycle.run('prompts:duplicateSelected', async () => {
        const ids = host.components.selectionController.list();
        if (!ids.length) {
            return;
        }
        for (const id of ids) {
            const source = host.operations.findPromptById(id);
            if (!source) {
                continue;
            }
            const nameBase = toTrimmedString(source.name || i18n.t('prompts.unnamedPrompt'));
            const created = await host.owners.streaming.runTask(
                'prompts.duplicate',
                () =>
                    createPromptRecord(
                        host,
                        {
                            name: i18n.t('prompts.duplicateName', { name: nameBase }),
                            content: source.content ?? '',
                            color: source.color ?? null
                        },
                        'PromptsPage.duplicatePrompt'
                    ),
                { displayName: i18n.t('prompts.actions.duplicateSelected'), rethrow: false }
            );
            if (!created) {
                continue;
            }
            host.operations.upsertPromptRecord(created);
        }
        host.components.selectionController.clear();
        if (host.components.selectionController.isActive()) {
            host.components.selectionController.toggleMode();
        }
        host.operations.reapplyCollection({ shouldRender: true, updateStats: true, updateFilters: false });
        save.notifyChanged();
    });
};

const downloadSelectedPrompts = (host: PromptsPageActionsHost): void => {
    const ids = host.components.selectionController.list();
    if (!ids.length) {
        return;
    }
    const entries = ids
        .map((id) => host.operations.findPromptById(id))
        .filter((prompt): prompt is PromptRecord => Boolean(prompt))
        .map((prompt) => host.operations.buildPromptDownloadEntry(prompt))
        .filter((entry) => Boolean(entry));
    if (!entries.length) {
        return;
    }
    const content = entries.join('\n\n---\n\n');
    host.operations.downloadTextFile(content, host.operations.buildSelectionDownloadFilename(), 'text/plain');
    host.owners.feedback.show(i18n.t('prompts.notifications.promptsDownloaded'), 'download');
};

export { cancelEditing, createDraftPromptCard, downloadSelectedPrompts, duplicateSelected, handleCardColorSelection, isDraftPromptId, saveEditing, setupUnsavedChangesGuard, startEditing };
export type { PromptsPageActionsHost };
