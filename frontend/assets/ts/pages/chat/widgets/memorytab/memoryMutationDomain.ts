/* SoAI - Memory text persistence and confirmed deletion [frontend/assets/ts/pages/chat/widgets/memorytab/memoryMutationDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ManagedMemoryEntry } from '@core/api/contracts/webuiMemoryContracts.ts';
import { readApiErrorDetail } from '@core/api/errorPayloads.ts';
import { APIError } from '@core/apiError.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import { createMutationRequestId } from '@core/mutations/mutationIdentity.ts';
import { downloadFile, sanitizeDownloadFilename } from '@core/primitives/download.ts';
import { copyTextWithBrowserClipboardFeedback } from '@core/ui/notifications/clipboardCopy.ts';
import { requireContentPreviewModalService } from '@core/ui/modals/contentpreview/service.ts';
import { createTextContentPreviewRequest } from '@core/ui/modals/contentpreview/requestFactories.ts';
import type { ContentPreviewTextDraftSnapshot, ContentPreviewTextSaveResult } from '@core/ui/modals/contentpreview/types.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import type { MemoryMutationHost } from '@pages/chat/widgets/memorytab/contracts.ts';

const memoryFailureMessage = (failure: Error): string => {
    const code = failure instanceof APIError ? failure.code : null;
    if (code === 'memory_revision_changed') return i18n.t('chat.memory.errors.revisionChanged');
    if (code === 'memory_duplicate_name') return i18n.t('chat.memory.errors.duplicateName');
    if (code === 'memory_duplicate_id') return i18n.t('chat.memory.errors.duplicateId');
    if (code === 'memory_profile_restricted') return i18n.t('chat.memory.errors.profileRestricted');
    if (code === 'memory_duplicate_relation') return i18n.t('chat.memory.errors.duplicateRelation');
    if (code === 'memory_relation_not_incident') return i18n.t('chat.memory.errors.relationNotIncident');
    if (code === 'memory_invalid_text' || code === 'memory_invalid_update' || code === 'memory_invalid_profile' || code === 'memory_invalid_revision') return i18n.t('chat.memory.errors.invalidText');
    if (code === 'memory_entry_missing' || code === 'memory_observation_missing' || code === 'memory_relation_missing' || code === 'memory_endpoint_missing') return i18n.t('chat.memory.errors.missing');
    return i18n.t('chat.memory.errors.unconfirmed');
};

const presentMemoryCommit = (host: MemoryMutationHost, entry?: ManagedMemoryEntry): void => {
    try {
        host.committed(entry);
    } catch (error) {
        errorHandler.error('MemoryLibrary', 'Confirmed memory commit presentation failed', ensureError(error));
        host.show(i18n.t('chat.memory.library.savedRefreshNeeded'), 'warning');
    }
};

const savedResult = (entry: ManagedMemoryEntry, observationId: string | null, content: string): ContentPreviewTextSaveResult => ({
    baseline: {
        title: entry.entity.name,
        content: entry.observations.find((observation) => observation.id === observationId)?.content ?? content,
        promptColor: null
    },
    sourceReference: null
});

const openMemoryTextEditor = (host: MemoryMutationHost, entry: ManagedMemoryEntry | null, observationId: string | null, mode: 'edit' | 'view' = 'edit'): void => {
    const editor = requireContentPreviewModalService();
    if (editor.isOpen()) return;
    const draftId = entry?.entity.id ?? createMutationRequestId();
    const observation = entry?.observations.find((candidate) => candidate.id === observationId);
    let savedEntry = entry;
    let editedObservationId = observationId;
    let reviewRequired = false;
    let unconfirmed = false;
    const persist = async (draft: ContentPreviewTextDraftSnapshot): Promise<ContentPreviewTextSaveResult | null> => {
        if (!host.isCurrent()) return null;
        if (reviewRequired || unconfirmed) {
            host.show(reviewRequired ? i18n.t('chat.memory.errors.revisionChanged') : i18n.t('chat.memory.errors.unconfirmed'), 'warning');
            return null;
        }
        let committed: ManagedMemoryEntry | null = null;
        try {
            committed = savedEntry ? await host.api.update(savedEntry.entity.id, { expectedRevision: savedEntry.revision, name: draft.title.trim(), observation: { id: editedObservationId, content: draft.content } }) : await host.api.create(draftId, draft.title.trim(), draft.content);
        } catch (error) {
            const failure = ensureError(error);
            if (!host.isCurrent()) {
                host.report(failure);
                return null;
            }
            const retryGuidance = readApiErrorDetail(failure, 'retry_guidance');
            if (failure instanceof APIError && failure.code === 'memory_revision_changed') reviewRequired = true;
            const definitiveRejection = failure instanceof APIError && failure.status >= 400 && failure.status < 500 && failure.code !== 'database_timeout';
            if (!definitiveRejection) {
                unconfirmed = true;
                if (retryGuidance !== 'do_not_retry' && (savedEntry === null || editedObservationId !== null)) {
                    try {
                        const current = await host.api.read(draftId);
                        const matches = current.observations.filter((fact) => fact.content === draft.content && (editedObservationId === null ? fact.source === 'manual' : fact.id === editedObservationId));
                        const matchedFact = matches.length === 1 ? matches[0] : null;
                        if (current.entity.name === draft.title.trim() && matchedFact) {
                            committed = current;
                            editedObservationId = matchedFact.id;
                        }
                    } catch (recoveryError) {
                        const recoveryFailure = ensureError(recoveryError);
                        if (!(recoveryFailure instanceof APIError)) errorHandler.warn('MemoryLibrary', 'Memory reconciliation read failed', recoveryFailure);
                    }
                }
            }
            if (!committed) {
                host.report(failure);
                return null;
            }
        }
        if (editedObservationId === null) {
            const previousIds = new Set(savedEntry?.observations.map((fact) => fact.id) ?? []);
            editedObservationId = committed.observations.find((fact) => !previousIds.has(fact.id))?.id ?? null;
        }
        savedEntry = committed;
        unconfirmed = false;
        const result = savedResult(committed, editedObservationId, draft.content);
        presentMemoryCommit(host, committed);
        return result;
    };
    editor.open(
        createTextContentPreviewRequest({
            scope: 'chat',
            type: 'text',
            headerDescription: entry ? `${i18n.t('chat.memory.viewer.observations')}: ${entry.observations.length} · ${i18n.t('chat.memory.viewer.relations')}: ${entry.relations.length}` : null,
            baseline: { title: entry?.entity.name ?? '', content: observation?.content ?? '', promptColor: null },
            editable: !observation?.profileField,
            isUnsavedDraft: entry === null,
            languageMode: 'default',
            disableCopyWhenEmpty: true,
            disableDownloadWhenEmpty: true,
            colorToolkit: null,
            onRequestSave: persist,
            onRequestDownload: () => {
                if (!host.isCurrent()) return;
                const content = savedEntry?.observations.find((fact) => fact.id === editedObservationId)?.content ?? '';
                downloadFile(content, `${sanitizeDownloadFilename(savedEntry?.entity.name, i18n.t('contentPreview.fields.text'))}.txt`, 'text/plain');
            },
            onRequestCopy: async (text) => {
                if (!host.isCurrent()) return;
                await copyTextWithBrowserClipboardFeedback({ showNotification: (message, type) => host.show(message, type === 'copy' ? 'success' : type === 'warning' ? 'warning' : 'error') }, { text, preserveText: true, successMessage: i18n.t('common.clipboard.copied') });
            },
            enhance: null,
            openSourceUrl: null,
            onStatePotentiallyChanged: null,
            validateDraft: (draft): boolean => {
                if (draft.title.trim() && draft.content.trim()) return true;
                host.show(i18n.t('chat.memory.errors.invalidText'), 'error');
                return false;
            }
        })
    );
    if (mode === 'edit') editor.enterEditMode();
};

const deleteMemoryRecord = async (host: MemoryMutationHost, entry: ManagedMemoryEntry, child: { type: 'observation' | 'relation'; id: string } | null): Promise<boolean> => {
    const confirmed = await requireDialogsService().showConfirmation({
        title: i18n.t('common.delete'),
        message: child ? i18n.t('chat.memory.library.deleteFact') : i18n.t('chat.memory.library.deleteEntry', { title: entry.entity.name, facts: entry.observations.length, relations: entry.relations.length }),
        confirmText: i18n.t('common.delete'),
        cancelText: i18n.t('common.cancel')
    });
    if (!confirmed || !host.isCurrent()) return false;
    try {
        if (child?.type === 'observation') await host.api.deleteObservation(entry.entity.id, child.id, entry.revision);
        else if (child?.type === 'relation') await host.api.deleteRelation(entry.entity.id, child.id, entry.revision);
        else await host.api.delete(entry.entity.id, entry.revision);
        presentMemoryCommit(host);
        return true;
    } catch (error) {
        host.report(ensureError(error));
        return false;
    }
};

export { presentMemoryCommit, deleteMemoryRecord, memoryFailureMessage, openMemoryTextEditor };
