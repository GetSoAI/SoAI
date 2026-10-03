/* SoAI - Prompts page effects [frontend/assets/ts/pages/prompts/controllers/page/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { generateSecureId } from '@core/primitives/idGenerator.ts';
import type { SaveController } from '@core/save/public.ts';
import type { PromptRecord } from '@features/prompts/public.ts';
import { createPromptRecord, updatePromptRecord } from '@pages/prompts/controllers/page/promptRecordManager.ts';
import { hasPromptCardEditChanges } from '@pages/prompts/controllers/page/saveDirtyStateManager.ts';
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
    const color = current === candidate ? null : candidate;
    host.components.colorToolkit.applyToCard(card, color);
    if (host.state.editingDraft?.promptId === promptId) host.state.editingDraft.color = color;
    save.notifyChanged();
};

const createDraftPromptCard = async (host: PromptsPageActionsHost, save: SaveController): Promise<void> => {
    const collectionView = host.owners.collections.view;
    if (!collectionView?.revealItem) throw new Error('Prompts collection cannot reveal a new prompt');
    let draftId = host.state.draftPromptId;
    if (draftId) {
        if (host.state.editingDraft?.promptId !== draftId) {
            const draft = host.operations.findPromptById(draftId);
            if (!draft) throw new Error('Prompt draft is unavailable');
            host.state.editingDraft = { promptId: draft.id, name: draft.name, content: draft.content, color: host.components.colorToolkit.normalize(draft.color), createdAtMs: draft.createdAtMs, modifiedAtMs: draft.modifiedAtMs };
        }
        host.state.editingPromptId = draftId;
        host.owners.collections.view?.markDirty?.([draftId]);
    } else {
        if (host.state.editingPromptId && hasPromptCardEditChanges(host)) {
            host.owners.feedback.show(i18n.t('prompts.unsavedChanges'), 'warning');
            return;
        }
        if (host.state.editingPromptId) host.owners.collections.view?.markDirty?.([host.state.editingPromptId]);
        const createdAtMs = Date.now();
        draftId = generateSecureId({ prefix: DRAFT_PROMPT_ID_PREFIX, separator: '' });
        host.state.draftPromptId = draftId;
        host.state.editingPromptId = draftId;
        const draft: PromptRecord = { id: draftId, name: i18n.t('prompts.unnamedPrompt'), content: '', color: null, createdAtMs, modifiedAtMs: createdAtMs };
        host.state.editingDraft = { promptId: draftId, name: draft.name, content: draft.content, color: draft.color, createdAtMs, modifiedAtMs: createdAtMs };
        host.operations.upsertItem(draft);
        host.operations.reapplyCollection({ shouldRender: true, updateStats: true, updateFilters: false });
        save.notifyChanged();
    }
    await collectionView.revealItem(draftId);
};

const discardDraftPromptCard = (host: PromptsPageActionsHost, promptId: string): void => {
    if (!isDraftPromptId(promptId)) return;
    if (host.state.draftPromptId === promptId) host.state.draftPromptId = null;
    host.operations.removeItemById(promptId);
};

const startEditing = async (host: PromptsPageActionsHost, save: SaveController, promptId: string): Promise<void> => {
    if (!promptId) {
        return;
    }
    if (host.state.editingPromptId && host.state.editingPromptId !== promptId) {
        if (hasPromptCardEditChanges(host)) {
            host.owners.feedback.show(i18n.t('prompts.unsavedChanges'), 'warning');
            return;
        }
        host.owners.collections.view?.markDirty?.([host.state.editingPromptId]);
        host.state.editingPromptId = null;
    }
    if (host.state.editingDraft?.promptId !== promptId) {
        const prompt = host.operations.findPromptById(promptId);
        if (!prompt) throw new Error(`Prompt "${promptId}" is not available for editing`);
        host.state.editingDraft = { promptId, name: prompt.name, content: prompt.content, color: host.components.colorToolkit.normalize(prompt.color), createdAtMs: prompt.createdAtMs, modifiedAtMs: prompt.modifiedAtMs };
    }
    host.state.editingPromptId = promptId;
    host.owners.collections.view?.markDirty?.([promptId]);
    save.notifyChanged();
};

const cancelEditing = async (host: PromptsPageActionsHost, save: SaveController, promptId: string): Promise<void> => {
    if (!promptId || host.state.editingPromptId !== promptId) {
        return;
    }
    const isDraft = host.state.draftPromptId === promptId;
    host.state.editingPromptId = null;
    host.state.editingDraft = null;
    if (isDraft) {
        discardDraftPromptCard(host, promptId);
        host.operations.reapplyCollection({ shouldRender: true, updateStats: true, updateFilters: false });
    } else {
        host.owners.collections.view?.markDirty?.([promptId]);
    }
    save.notifyChanged();
};

const saveEditing = async (host: PromptsPageActionsHost, promptId: string): Promise<void> => {
    await host.owners.pageLifecycle.run('prompts:saveEditing', async () => {
        const isDraft = host.state.draftPromptId === promptId;
        const existing = host.operations.findPromptById(promptId);
        if (!existing) {
            host.state.editingPromptId = null;
            host.state.editingDraft = null;
            discardDraftPromptCard(host, promptId);
            host.operations.reapplyCollection({ shouldRender: true, updateStats: true, updateFilters: false });
            return;
        }
        if (!isDraft && !hasPromptCardEditChanges(host)) {
            host.state.editingPromptId = null;
            host.state.editingDraft = null;
            host.owners.collections.view?.markDirty?.([promptId]);
            return;
        }
        const editingDraft = host.state.editingDraft;
        if (!editingDraft || editingDraft.promptId !== promptId) throw new Error('Prompt edit state is unavailable');
        const payload = {
            name: toTrimmedString(editingDraft.name),
            content: editingDraft.content,
            color: host.components.colorToolkit.normalize(editingDraft.color)
        };

        const saved = isDraft ? await host.owners.streaming.runTask('prompts.create', () => createPromptRecord(host, payload, 'PromptsPage.createPrompt'), { displayName: i18n.t('prompts.actions.createPrompt'), rethrow: false }) : await host.owners.streaming.runTask('prompts.update', () => updatePromptRecord(host, promptId, payload, 'PromptsPage.updatePrompt'), { displayName: i18n.t('prompts.actions.save'), rethrow: false });
        if (!saved) {
            return;
        }
        discardDraftPromptCard(host, promptId);
        host.operations.upsertPromptRecord(saved);
        if (host.state.editingPromptId === promptId && host.state.editingDraft === editingDraft) {
            if (isDraft) {
                editingDraft.promptId = saved.id;
                host.state.editingPromptId = saved.id;
            }
            if (!hasPromptCardEditChanges(host)) {
                host.state.editingPromptId = null;
                host.state.editingDraft = null;
            }
        }
        host.owners.collections.view?.markDirty?.([saved.id]);
        await host.owners.collections.view?.revealItem?.(saved.id);
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
