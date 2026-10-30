/* SoAI - Memory relationship form ownership [frontend/assets/ts/pages/chat/widgets/memorytab/memoryRelationshipDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ManagedMemoryEntry } from '@core/api/contracts/webuiMemoryContracts.ts';
import { APIError } from '@core/apiError.ts';
import { dom } from '@core/dom/dom.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { FieldStateTracker } from '@core/forms/fieldStateTracker.ts';
import { setFieldErrorMessage } from '@core/ui/forms/fieldError.ts';
import { i18n } from '@core/i18n/index.ts';
import { createSaveController } from '@core/save/public.ts';
import { createBusyDisabledToken, setBusyDisabledState } from '@core/ui/controls/busyDisabledState.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { uiHtml, uiAttr, uiText } from '@core/security/uiHtml.ts';
import type { MemoryMutationHost } from '@pages/chat/widgets/memorytab/contracts.ts';
import { memoryFailureMessage, presentMemoryCommit } from '@pages/chat/widgets/memorytab/memoryMutationDomain.ts';

const editMemoryRelationship = async (host: MemoryMutationHost, entry: ManagedMemoryEntry, relationId: string, entries: readonly ManagedMemoryEntry[]): Promise<void> => {
    const relation = entry.relations.find((candidate) => candidate.id === relationId);
    if (!relation) return;
    const fields = dom.getDocument().createElement('div');
    dom.setHTML(fields, uiHtml`<div class="form-group setting-change-surface"><label for="memory-relation-from">${uiText(i18n.t('chat.memory.library.from'))}</label><select id="memory-relation-from" class="form-select"></select></div><div class="form-group setting-change-surface"><label for="memory-relation-to">${uiText(i18n.t('chat.memory.library.to'))}</label><select id="memory-relation-to" class="form-select"></select></div><div class="form-group setting-change-surface"><label for="memory-relation-type">${uiText(i18n.t('chat.memory.library.type'))}</label><input id="memory-relation-type" class="form-input" value="${uiAttr(relation.relationType)}" /></div>`);
    const fromSelect = dom.resolve('#memory-relation-from', fields);
    const toSelect = dom.resolve('#memory-relation-to', fields);
    const typeInput = dom.resolve('#memory-relation-type', fields);
    if (!(fromSelect instanceof HTMLSelectElement) || !(toSelect instanceof HTMLSelectElement) || !(typeInput instanceof HTMLInputElement)) throw new Error('Memory relationship form is incomplete');
    const endpoints = new Map(entries.map((candidate): [string, string] => [candidate.entity.id, candidate.entity.name]));
    endpoints.set(relation.fromEntityId, relation.fromEntity);
    endpoints.set(relation.toEntityId, relation.toEntity);
    for (const select of [fromSelect, toSelect]) {
        for (const [id, name] of endpoints) {
            const option = fields.ownerDocument.createElement('option');
            option.value = id;
            option.textContent = name;
            select.append(option);
        }
    }
    fromSelect.value = relation.fromEntityId;
    toSelect.value = relation.toEntityId;
    const fieldError = fields.ownerDocument.createElement('div');
    fieldError.id = 'memory-relation-error';
    fields.append(fieldError);
    const tracker = new FieldStateTracker({ getElement: (key) => dom.resolve(`#memory-relation-${key}`, fields) });
    const relationType = (): string => typeInput.value.trim();
    const hasChanges = (): boolean => fromSelect.value !== relation.fromEntityId || toSelect.value !== relation.toEntityId || relationType() !== relation.relationType;
    let saved = false;
    let blockedMessage: string | null = null;
    const controller = createSaveController({
        headerContextId: 'memory-relationship',
        requestContextLabel: 'Memory relationship save',
        units: [
            {
                id: 'memory-relationship',
                hasChanges,
                isValid: () => blockedMessage === null && host.isCurrent() && relationType().length > 0 && [fromSelect.value, toSelect.value].includes(entry.entity.id),
                prepare: () => {
                    const payload = { expectedRevision: entry.revision, fromEntityId: fromSelect.value, toEntityId: toSelect.value, relationType: relationType() };
                    return {
                        isValid: host.isCurrent,
                        save: async () => {
                            const controls = [fromSelect, toSelect, typeInput].map((control) => ({ control, token: setBusyDisabledState(control, { isBusy: true, createToken: createBusyDisabledToken, spinner: 'none' }) }));
                            const present = host.captureCommitPresentation();
                            try {
                                const committed = await host.api.updateRelation(entry.entity.id, relationId, payload);
                                saved = true;
                                presentMemoryCommit(host, present, committed);
                                return;
                            } catch (error) {
                                const failure = ensureError(error);
                                const definitiveRejection = failure instanceof APIError && failure.status >= 400 && failure.status < 500 && failure.code !== 'database_timeout';
                                if (!definitiveRejection || (failure instanceof APIError && failure.code === 'memory_revision_changed')) blockedMessage = memoryFailureMessage(failure);
                                host.report(failure);
                                return { type: 'stop' };
                            } finally {
                                for (const { control, token } of controls) setBusyDisabledState(control, { isBusy: false, token });
                            }
                        }
                    };
                },
                save: () => ({ type: 'stop' })
            }
        ]
    });
    fields.addEventListener('input', () => {
        const message = relationType() ? null : i18n.t('chat.memory.errors.invalidText');
        setFieldErrorMessage(typeInput, fieldError, message);
        tracker.setInvalid('type', message);
        tracker.update('type', { currentValue: relationType(), originalValue: relation.relationType });
        controller.notifyChanged();
    });
    fields.addEventListener('change', () => {
        tracker.update('from', { currentValue: fromSelect.value, originalValue: relation.fromEntityId });
        tracker.update('to', { currentValue: toSelect.value, originalValue: relation.toEntityId });
        controller.notifyChanged();
    });
    try {
        await requireDialogsService().showConfirmation({
            title: i18n.t('chat.memory.viewer.relations'),
            fields,
            confirmText: i18n.t('common.save'),
            cancelText: i18n.t('common.cancel'),
            onConfirm: async () => {
                if (!host.isCurrent()) return false;
                if (blockedMessage !== null) {
                    host.show(blockedMessage, 'warning');
                    return false;
                }
                if (!relationType() || ![fromSelect.value, toSelect.value].includes(entry.entity.id)) {
                    const message = !relationType() ? i18n.t('chat.memory.errors.invalidText') : i18n.t('chat.memory.errors.relationNotIncident');
                    setFieldErrorMessage(typeInput, fieldError, message);
                    return false;
                }
                if (!hasChanges()) return true;
                await controller.requestSave();
                return saved && host.isCurrent();
            }
        });
    } finally {
        controller.dispose();
    }
};

export { editMemoryRelationship };
