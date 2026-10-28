/* SoAI - Skill library operations and staged conversation selection [frontend/assets/ts/features/chat/conversationsettings/skills/controller.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { downloadAuthenticatedResponse } from '@core/api/authenticatedDownload.ts';
import { getAuthManager } from '@core/auth/public.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { notifyHandledOperationError } from '@core/operationErrorNotifier.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { bindDataActionListener, type DataActionEventType } from '@core/dom/dataActionBinding.ts';
import { dom, narrowHTMLElement, narrowInput } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import type { SkillLibrary } from '@core/api/contracts/webuiSkillContractTypes.ts';
import { requireSkillIds } from '@core/api/contracts/webuiSkillContracts.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { CHAT_CONFIGURATION_MODAL_ID } from '@features/chat/modals/constants.ts';
import type { ConversationSettingsHost } from '@features/chat/conversationsettings/conversationSettingsHost.ts';
import { applyConversationSettingsUpdate } from '@features/chat/conversationsettings/effects.ts';
import { SkillSelectionDraft } from '@features/chat/conversationsettings/skills/selectionDraft.ts';
import { SkillSettingsResources } from '@features/chat/conversationsettings/skills/resources.ts';
import { SkillSettingsView } from '@features/chat/conversationsettings/skills/view.ts';
import { SkillImportOperation } from '@features/chat/conversationsettings/skills/importOperation.ts';
import { isSkillAction, type SkillAction } from '@features/chat/conversationsettings/skills/actionIds.ts';

class SkillsConversationSettingsController {
    readonly #host: ConversationSettingsHost;
    readonly #changed: (dirty: boolean, valid: boolean) => void;
    readonly #draft = new SkillSelectionDraft();
    readonly #session = new SequenceToken();
    readonly #update = new SequenceToken();
    readonly #details = new SequenceToken();
    readonly #imports: SkillImportOperation;
    #view: SkillSettingsView | null = null;
    #resources: SkillSettingsResources | null = null;
    #library: SkillLibrary | null = null;
    #conversationId: string | null = null;
    #fresh = false;
    #loading = false;
    #renderPending = false;

    constructor(host: ConversationSettingsHost, changed: (dirty: boolean, valid: boolean) => void) {
        this.#host = host;
        this.#changed = changed;
        this.#imports = new SkillImportOperation(host.data.api.webui.chat.skills, () => getAuthManager().getCurrentUser()?.id ?? null);
    }

    bindEvents(modal: HTMLElement): Array<() => void> {
        const pane = dom.resolve(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'skills-content'), modal);
        if (!pane) throw new Error('Skill settings pane is missing.');
        const root = narrowHTMLElement(pane, 'Skill settings pane');
        this.#view = new SkillSettingsView(root, this.#host.view);
        const events = new AbortController();
        const eventTypes: readonly DataActionEventType[] = ['click', 'change', 'input'];
        for (const eventType of eventTypes) {
            bindDataActionListener({
                root,
                signal: events.signal,
                eventType,
                isAction: isSkillAction,
                preventDefault: 'never',
                ignoreDisabled: true,
                onAction: ({ action, actionElement }) => {
                    const expected = action === 'skills-search' ? 'input' : action === 'skills-upload' || action === 'skills-toggle' ? 'change' : 'click';
                    if (eventType !== expected) return;
                    if (action === 'skills-add') {
                        this.#view?.upload.click();
                        return;
                    }
                    if (action === 'skills-search') {
                        this.#render();
                        return;
                    }
                    if (action === 'skills-toggle') {
                        const input = narrowInput(actionElement, 'Skill selection');
                        const identity = input.dataset['skillId'];
                        if (!identity) throw new Error('Skill toggle identity is missing.');
                        this.#draft.stage(input.checked ? [...this.#draft.selected, identity] : this.#draft.selected.filter((selected) => selected !== identity));
                        this.#sync();
                        return;
                    }
                    const session = this.#session.value;
                    terminateHandledPromise(
                        this.#host.workflow
                            .runWithBoundary('chat:skills', () => this.#perform(action, actionElement))
                            .catch((error: Error) => {
                                if (!this.#session.isActive(session) || isAbortError(error)) return;
                                if (!notifyHandledOperationError(error)) {
                                    if (this.#imports.pending) this.#host.workflow.showNotification(i18n.t('chat.configuration.skills.importUncertain'), 'warning');
                                    else this.#host.workflow.showNotification(i18n.t('common.errors.operationFailed'), 'error');
                                }
                                throw error;
                            })
                    );
                }
            });
        }
        const resetOwner = (): void => {
            this.#imports.discardOwner();
            if (this.#view) this.#view.upload.value = '';
            this.close();
        };
        return [() => events.abort(), getAuthManager().onLogin(resetOwner), getAuthManager().onLogout(resetOwner)];
    }

    async open(conversationId: string | null): Promise<void> {
        this.close();
        this.#conversationId = conversationId;
        const session = this.#session.next();
        const resources = new SkillSettingsResources(conversationId, {
            library: (library) => {
                if (!this.#session.isActive(session)) return;
                this.#library = library;
                this.#draft.receiveLibrary(library);
                this.#sync();
            },
            selection: (selection) => {
                if (!this.#session.isActive(session)) return;
                this.#draft.receiveSelection(selection);
                this.#sync();
            },
            status: (library, selection) => {
                if (!this.#session.isActive(session)) return;
                this.#loading = library.status === 'initializing' || library.status === 'recovering' || selection?.status === 'initializing' || selection?.status === 'recovering';
                this.#fresh = library.status === 'ready' && (selection === null || selection.status === 'ready');
                this.#draft.setFresh(this.#fresh);
                this.#sync();
            }
        });
        this.#resources = resources;
        await resources.start();
    }

    close(): void {
        this.#session.invalidate();
        this.#update.invalidate();
        this.#details.invalidate();
        this.#resources?.dispose();
        this.#resources = null;
        this.#conversationId = null;
        this.#library = null;
        this.#fresh = false;
        this.#loading = false;
        this.#draft.reset();
        this.#view?.clearDetails();
        this.#sync();
    }

    dispose(): void {
        this.#imports.discardOwner();
        if (this.#view) this.#view.upload.value = '';
        this.close();
        this.#view?.dispose();
        this.#view = null;
    }
    isHydrated(): boolean {
        return this.#fresh;
    }
    refreshWorkingPresentation(): void {
        this.#render();
    }

    isEditable(): boolean {
        return this.#conversationId !== null && this.#draft.baseline !== null;
    }
    isDirty(): boolean {
        return this.#draft.dirty;
    }
    resolvePreset(section: JsonObject): { section: JsonObject | null; skippedValues: string[] } {
        const identities = requireSkillIds(section['skill_ids']);
        const available = new Set(this.#library?.skills.filter((skill) => !skill.disableModelInvocation || skill.userInvocable).map((skill) => skill.skillId) ?? []);
        const retained = identities.filter((identity) => available.has(identity));
        return { section: identities.length > 0 && retained.length === 0 ? null : { 'skill_ids': retained }, skippedValues: identities.filter((identity) => !available.has(identity)).map((identity) => `skills:skill_ids:${identity}`) };
    }
    workingSection(): JsonObject | null {
        return this.isEditable() ? { 'skill_ids': [...this.#draft.selected] } : null;
    }
    stageSection(section: JsonObject): void {
        this.#draft.stage(requireSkillIds(section['skill_ids']));
        this.#sync();
    }

    prepareSave(isPresentationActive: () => boolean): (() => Promise<void>) | null {
        if (!this.#draft.dirty || !this.#draft.valid) return null;
        const intent = this.#draft.capture();
        const session = this.#session.value;
        return async () => {
            const updateToken = this.#update.next();
            await applyConversationSettingsUpdate({
                conversationId: intent.conversationId,
                updateToken,
                isUpdateTokenActive: (token) => this.#update.isActive(token) && this.#session.isActive(session) && isPresentationActive(),
                isStillActive: () => this.#conversationId === intent.conversationId,
                boundary: 'chat:skillsSave',
                updateRequest: async () => {
                    try {
                        return await this.#host.data.api.webui.chat.skills.replaceSelection(intent.conversationId, intent.revision, intent.skillIds);
                    } catch (error) {
                        if (this.#session.isActive(session)) this.#resources?.invalidateSelection();
                        throw error;
                    }
                },
                onAcceptedSuccess: (selection) => {
                    if (!this.#session.isActive(session)) return;
                    this.#resources?.acceptedSelection(selection);
                    this.#host.workflow.refreshTokenCounterPreview();
                },
                onSuccess: (selection) => {
                    this.#draft.acceptSave(intent, selection);
                    this.#sync();
                },
                runWithBoundary: (name, request) => this.#host.workflow.runWithBoundary(name, request),
                errorMessage: i18n.t('common.error'),
                failureMessage: i18n.t('common.error'),
                successMessage: i18n.t('common.success'),
                showNotification: (message, type) => this.#host.workflow.showNotification(message, type),
                onFinally: () => this.#sync()
            });
        };
    }

    async #perform(action: SkillAction, element: HTMLElement): Promise<void> {
        const session = this.#session.value;
        const resources = this.#resources;
        if (action === 'skills-close-details') {
            this.#details.invalidate();
            this.#view?.clearDetails();
            return;
        }
        if (action === 'skills-keep') {
            this.#draft.reviewLatest(true);
            this.#sync();
            return;
        }
        if (action === 'skills-reload') {
            if (this.#imports.pending) await this.#importPending();
            if (!this.#session.isActive(session)) return;
            await resources?.refresh();
            if (!this.#session.isActive(session)) return;
            if (this.#draft.baseline) this.#draft.reviewLatest(false);
            this.#sync();
            return;
        }
        if (action === 'skills-upload') {
            const file = narrowInput(element, 'Skill upload').files?.[0];
            if (!file || this.#imports.busy) return;
            this.#imports.stage(file);
            await this.#importPending();
            return;
        }
        const identity = element.dataset['skillId'];
        if (!identity) throw new Error('Skill action identity is missing.');
        if (action === 'skills-download') {
            const path = element.dataset['skillPath'];
            if (!path) throw new Error('Skill resource path is missing.');
            const response = await this.#host.data.api.webui.chat.skills.resource(identity, path);
            if (this.#session.isActive(session)) await downloadAuthenticatedResponse(response);
            return;
        }
        if (action === 'skills-details') {
            const token = this.#details.next();
            const details = await this.#host.data.api.webui.chat.skills.details(identity);
            if (this.#session.isActive(session) && this.#details.isActive(token)) this.#view?.showDetails(details);
            return;
        }
        if (action === 'skills-remove') {
            const confirmed = await requireDialogsService().showConfirmation({ title: i18n.t('common.delete'), message: i18n.t('chat.configuration.skills.removeConfirm'), confirmText: i18n.t('common.delete'), confirmVariant: 'danger' });
            if (!confirmed || !this.#session.isActive(session)) return;
            await this.#host.data.api.webui.chat.skills.remove(identity);
            if (!this.#session.isActive(session)) return;
            this.#details.invalidate();
            this.#view?.clearDetails();
            await resources?.refresh();
        }
    }

    async #importPending(): Promise<void> {
        const session = this.#session.value;
        const resources = this.#resources;
        const view = this.#view;
        const operation = this.#imports.run();
        this.#sync();
        try {
            const receipt = await operation;
            if (receipt === null || !this.#session.isActive(session) || this.#resources !== resources || this.#view !== view) return;
            await resources?.refresh();
        } finally {
            if (this.#session.isActive(session) && this.#view === view && !this.#imports.pending && view) view.upload.value = '';
            this.#sync();
        }
    }

    #sync(): void {
        this.#changed(this.#draft.dirty, this.#draft.valid);
        if (this.#renderPending) return;
        this.#renderPending = true;
        queueMicrotask(() => {
            this.#renderPending = false;
            this.#render();
        });
    }

    #render(): void {
        this.#view?.render(this.#library, this.#draft, { editable: this.isEditable(), fresh: this.#fresh, busy: this.#imports.busy, retryImport: this.#imports.pending, loading: this.#loading });
    }
}

export { SkillsConversationSettingsController };
