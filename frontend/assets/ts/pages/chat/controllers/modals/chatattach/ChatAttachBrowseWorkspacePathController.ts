/* SoAI - Chat attach modal browse workspace path controller [frontend/assets/ts/pages/chat/controllers/modals/chatattach/ChatAttachBrowseWorkspacePathController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AttachmentAcquisitionScope } from '@core/attachments/protocols.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError, requireErrorMessage } from '@core/errors/coerce.ts';
import { APIError } from '@core/apiError.ts';
import { showFolderPickerModal } from '@core/fileexplorerbrowser/folderPickerModal.ts';
import { resolveFolderPickerPathOverride } from '@core/fileexplorerbrowser/folderPickerPathOverride.ts';
import { buildFolderPickerLabels } from '@core/fileexplorerbrowser/folderPickerLabels.ts';
import { isAbsoluteFilesystemPath } from '@core/filePathResolution.ts';
import { resolveWorkspaceBrowserAccess } from '@core/fileexplorerbrowser/workspaceBrowserAccess.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedStringOrNull } from '@core/normalize.ts';
import { isChatConversationSettingsWritable, parseConversationWorkspacePathConfig, type Conversation, type ConversationWorkspacePathConfig } from '@features/chat/public.ts';
import type { ChatAttachWorkspacePathHost } from '@pages/chat/controllers/modals/chatattach/contracts.ts';
import type { AttachBrowseElements } from '@features/attachmodal/public.ts';

class ChatAttachBrowseWorkspacePathController {
    readonly #host: ChatAttachWorkspacePathHost;
    readonly #elements: AttachBrowseElements;
    readonly #onChanged: () => Promise<void>;
    readonly #syncToken = new SequenceToken();
    #active = false;
    #config: ConversationWorkspacePathConfig | null = null;

    constructor(host: ChatAttachWorkspacePathHost, elements: AttachBrowseElements, onChanged: () => Promise<void>) {
        this.#host = host;
        this.#elements = elements;
        this.#onChanged = onChanged;
    }

    activate(): void {
        this.#active = true;
        this.#host.execution.run('chat:attachModalBrowseWorkspacePathLoad', () => this.refresh());
    }

    deactivate(): void {
        this.#active = false;
        this.#syncToken.invalidate();
    }

    async refresh(): Promise<void> {
        const conversation = this.#host.conversation.current();
        const conversationId = toTrimmedStringOrNull(conversation?.id);
        if (!isChatConversationSettingsWritable(conversation) || conversationId === null) {
            this.#config = null;
            this.#renderNoConversation();
            return;
        }
        const scope = this.#host.attachments.captureIntake().scope;
        const token = this.#syncToken.next();
        this.#renderLoading();
        try {
            const payload = await this.#host.shared.api.webui.chat.workspacePath.getConfig(conversationId);
            if (!scope.isCurrent() || !this.#isCurrent(token, conversationId)) {
                return;
            }
            const config = parseConversationWorkspacePathConfig(payload);
            this.#config = config;
            this.#host.conversation.updateWorkspacePath(conversationId, config);
            this.#applyConfig(config);
        } catch (error) {
            if (!scope.isCurrent() || !this.#isCurrent(token, conversationId)) {
                return;
            }
            this.#config = null;
            this.#renderError();
            this.#host.shared.feedback.show(i18n.t('chat.configuration.filesFolder.loadFailed'), 'error');
            throw ensureError(error);
        }
    }

    async openPicker(scope: AttachmentAcquisitionScope): Promise<void> {
        const conversation = this.#host.conversation.current();
        const conversationId = toTrimmedStringOrNull(conversation?.id);
        if (!isChatConversationSettingsWritable(conversation) || conversationId === null) {
            return;
        }
        const config = this.#config;
        if (config === null) {
            this.#host.shared.feedback.show(i18n.t('chat.configuration.filesFolder.loadingHint'), 'warning');
            return;
        }
        const token = this.#syncToken.value;
        if (!scope.isCurrent() || !this.#isCurrent(token, conversationId)) return;
        const chatApi = this.#host.shared.api;
        const access = await resolveWorkspaceBrowserAccess({
            getCurrentUser: () => chatApi.webui.auth.getMe(),
            scopedBrowserApi: chatApi.fileExplorer
        });
        if (!scope.isCurrent() || !this.#isCurrent(token, conversationId)) return;
        const initialPath = typeof config.effectiveWorkspacePath === 'string' && config.effectiveWorkspacePath.trim() ? config.effectiveWorkspacePath.trim() : undefined;
        const initialPathIsAbsolute = initialPath ? isAbsoluteFilesystemPath(initialPath) : false;
        const result = await showFolderPickerModal({
            source: { type: 'workspace', api: access.browserApi },
            title: i18n.t('chat.configuration.filesFolder.pickerTitle'),
            message: i18n.t('chat.configuration.filesFolder.pickerMessage'),
            labels: buildFolderPickerLabels({
                chooseCurrent: i18n.t('common.save')
            }),
            allowManualPathEntry: true,
            ...(initialPath && initialPathIsAbsolute ? { initialAbsolutePathToBrowse: initialPath } : {}),
            ...(initialPath && !initialPathIsAbsolute ? { initialVirtualPath: initialPath } : {})
        });
        if (!scope.isCurrent() || !this.#isCurrent(token, conversationId)) return;
        if (!result || result.resultType !== 'selected') {
            return;
        }
        const nextOverride = resolveFolderPickerPathOverride(result);
        if (nextOverride === undefined) {
            this.#host.shared.feedback.show(i18n.t('chat.configuration.filesFolder.invalidHint'), 'error');
            return;
        }
        const activeConversation = this.#host.conversation.current();
        if (!isChatConversationSettingsWritable(activeConversation) || activeConversation.id !== conversationId) {
            return;
        }
        await this.#applyOverrideUpdate(activeConversation, conversationId, nextOverride, scope);
    }

    async #applyOverrideUpdate(conversation: Conversation, conversationId: string, nextOverride: string | null, scope: AttachmentAcquisitionScope): Promise<void> {
        if (!isChatConversationSettingsWritable(conversation)) {
            return;
        }
        const token = this.#syncToken.next();
        let applied = false;
        this.#renderSaving();
        this.#elements.workspacePathButton.disabled = true;
        try {
            await this.#host.execution.boundary('chat:attachModalWorkspacePathUpdate', async () => {
                const activeConversation = this.#host.conversation.current();
                if (!scope.isCurrent() || !this.#isCurrent(token, conversationId) || !isChatConversationSettingsWritable(activeConversation) || activeConversation.id !== conversationId) {
                    return;
                }
                await this.#host.conversation.actions.ensureConversationPersisted(activeConversation);
                if (!scope.isCurrent() || !this.#isCurrent(token, conversationId)) return;
                const payload = await this.#host.shared.api.webui.chat.workspacePath.updateConfig(conversationId, {
                    workspacePath: nextOverride
                });
                if (!scope.isCurrent() || !this.#isCurrent(token, conversationId)) {
                    return;
                }
                const config = parseConversationWorkspacePathConfig(payload);
                this.#config = config;
                this.#host.conversation.updateWorkspacePath(conversationId, config);
                this.#applyConfig(config);
                applied = true;
            });
        } catch (error) {
            if (!scope.isCurrent() || !this.#isCurrent(token, conversationId)) {
                return;
            }
            const runtimeError = ensureError(error);
            errorHandler.warn('ChatAttachBrowseWorkspacePathController', 'Workspace path save failed', runtimeError);
            const apiMessage = runtimeError instanceof APIError && runtimeError.status === 422 ? requireErrorMessage(runtimeError, '') : '';
            this.#host.shared.feedback.show(apiMessage || i18n.t('chat.configuration.filesFolder.saveFailed'), 'error');
            if (this.#config !== null) {
                this.#applyConfig(this.#config);
                return;
            }
            this.#renderError();
            return;
        }
        if (!applied || !this.#isCurrent(token, conversationId) || this.#host.conversation.current() !== conversation) return;
        this.#elements.workspacePathButton.disabled = false;
        await this.#onChanged();
        if (!this.#isCurrent(token, conversationId) || this.#host.conversation.current() !== conversation) return;
        this.#host.shared.feedback.show(nextOverride ? i18n.t('chat.configuration.filesFolder.savedOverride') : i18n.t('chat.configuration.filesFolder.savedInherited'), 'success');
    }

    #applyConfig(config: ConversationWorkspacePathConfig): void {
        this.#elements.workspacePathButton.disabled = false;
        this.#elements.workspacePathInput.value = config.effectiveWorkspacePath?.trim() || '/';
    }

    #renderNoConversation(): void {
        this.#elements.workspacePathButton.disabled = true;
        this.#elements.workspacePathInput.value = '/';
    }

    #renderLoading(): void {
        this.#elements.workspacePathButton.disabled = true;
    }

    #renderSaving(): void {
        this.#elements.workspacePathButton.disabled = true;
    }

    #renderError(): void {
        this.#elements.workspacePathButton.disabled = false;
    }

    #isCurrent(token: number, conversationId: string): boolean {
        return this.#active && this.#syncToken.isActive(token) && this.#host.conversation.currentId() === conversationId;
    }
}

export { ChatAttachBrowseWorkspacePathController };
