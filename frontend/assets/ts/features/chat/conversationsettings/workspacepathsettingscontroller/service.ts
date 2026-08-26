/* SoAI - Staged conversation workspace-path settings ownership [frontend/assets/ts/features/chat/conversationsettings/workspacepathsettingscontroller/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { i18n } from '@core/i18n/index.ts';
import { showFolderPickerModal, type FolderPickerResult } from '@core/fileexplorerbrowser/folderPickerModal.ts';
import { resolveFolderPickerPathOverride } from '@core/fileexplorerbrowser/folderPickerPathOverride.ts';
import { buildFolderPickerLabels } from '@core/fileexplorerbrowser/folderPickerLabels.ts';
import { isAbsoluteOsPath } from '@core/fileexplorerbrowser/paths.ts';
import { resolveWorkspaceBrowserAccess } from '@core/fileexplorerbrowser/workspaceBrowserAccess.ts';
import { setFieldSurfaceModified } from '@core/forms/fieldSurface.ts';
import { isChatConversationSettingsWritable } from '@features/chat/conversation/conversationSettingsEligibility.ts';
import type { ConversationModelSettingsUpdate } from '@core/chat/executionSettingsTypes.ts';
import type { ConversationWorkspacePathConfig } from '@features/chat/conversationsettings/settingsModels.ts';
import type { ConversationSettingsHost } from '@features/chat/conversationsettings/conversationSettingsHost.ts';
import { resolveWorkspacePathChangeButton, resolveWorkspacePathPathElement, resolveWorkspacePathResetButton, resolveWorkspacePathStatusElement } from '@features/chat/conversationsettings/workspacepathsettingscontroller/dom.ts';
import { resolveWorkspacePathInvalidStatusText } from '@features/chat/conversationsettings/workspacepathsettingscontroller/validationText.ts';
import { parseConversationWorkspacePathConfig } from '@features/chat/conversationsettings/conversationSettingsParsing.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';

class ConversationWorkspacePathSettingsController {
    readonly #host: ConversationSettingsHost;
    readonly #onDirtyStateChange: (hasChanges: boolean) => void;
    #modal: Element | null = null;
    #conversationId: string | null = null;
    #baseline: ConversationWorkspacePathConfig | null = null;
    #workingOverride: string | null = null;
    #derivedProjectionStale = false;
    readonly #onModalClick = (event: Event): void => {
        terminateHandledPromise(this.#handleClick(event));
    };

    constructor(options: { host: ConversationSettingsHost; onDirtyStateChange: (hasChanges: boolean) => void }) {
        this.#host = options.host;
        this.#onDirtyStateChange = options.onDirtyStateChange;
    }

    bindEvents(modal: Element): Array<() => void> {
        this.#modal = modal;
        const abortController = new AbortController();
        modal.addEventListener('click', this.#onModalClick, { signal: abortController.signal });
        return [() => abortController.abort()];
    }

    setConversation(conversationId: string | null): void {
        this.#conversationId = conversationId;
    }

    resetUI(): void {
        this.#baseline = null;
        this.#workingOverride = null;
        this.#derivedProjectionStale = false;
        this.#applyWorkingToUI();
        this.#onDirtyStateChange(false);
    }

    dispose(): void {
        this.#modal = null;
        this.#conversationId = null;
        this.#baseline = null;
        this.#workingOverride = null;
        this.#derivedProjectionStale = false;
    }

    syncFromConfig(config: ConversationWorkspacePathConfig | null): void {
        this.#baseline = config ? { ...config } : null;
        this.#workingOverride = config?.workspacePath ?? null;
        this.#derivedProjectionStale = false;
        this.#applyWorkingToUI();
        this.#onDirtyStateChange(false);
    }

    isHydrated(): boolean {
        return this.#baseline !== null;
    }

    isValid(): boolean {
        return this.canCommitWorkingOverride(this.#workingOverride);
    }

    isDirty(): boolean {
        return this.#baseline !== null && this.#workingOverride !== this.#baseline.workspacePath;
    }

    hasChanges(): boolean {
        return this.isDirty() || this.#derivedProjectionStale;
    }

    workingOverride(): string | null {
        return this.#workingOverride;
    }

    canCommitWorkingOverride(workspacePath: string | null): boolean {
        return workspacePath === null || isAbsoluteOsPath(workspacePath);
    }

    baselineConfig(): ConversationWorkspacePathConfig | null {
        return this.#baseline ? { ...this.#baseline } : null;
    }

    commitWorkingOverride(workspacePath: string | null): void {
        this.#workingOverride = workspacePath;
    }

    refreshWorkingPresentation(): void {
        this.#applyWorkingToUI();
        this.#onDirtyStateChange(this.hasChanges());
    }

    rebase(config: ConversationWorkspacePathConfig): void {
        this.#baseline = { ...config };
        this.#workingOverride = config.workspacePath;
        this.#derivedProjectionStale = false;
        this.refreshWorkingPresentation();
    }

    cancel(): void {
        if (!this.#baseline) {
            return;
        }
        this.#workingOverride = this.#baseline.workspacePath;
        this.refreshWorkingPresentation();
    }

    conversationPatch(): ConversationModelSettingsUpdate {
        return this.isDirty() && this.isValid() ? { workspacePath: this.#workingOverride } : {};
    }

    prepareConversationSave(isPresentationActive: () => boolean = () => true): () => Promise<boolean> {
        const conversation = this.#host.data.getCurrentConversation();
        const nextOverride = this.#workingOverride;
        const baseline = this.#baseline ? { ...this.#baseline } : null;
        if (!this.hasChanges() || !this.isValid() || !conversation || !isChatConversationSettingsWritable(conversation)) {
            return async () => true;
        }
        const conversationId = conversation.id;
        if (!conversationId) {
            throw new Error('Workspace path settings require a persisted conversation id.');
        }
        return async (): Promise<boolean> => {
            let config: ConversationWorkspacePathConfig;
            try {
                config = parseConversationWorkspacePathConfig(await this.#host.data.api.webui.chat.workspacePath.getConfig(conversationId));
            } catch (error) {
                if (!isPresentationActive() || this.#host.data.getCurrentConversation() !== conversation || this.#conversationId !== conversationId) return true;
                this.#retainStaleProjection(nextOverride, baseline);
                errorHandler.warn('ChatConversationSettings', 'Workspace path projection requires refresh', ensureError(error));
                return false;
            }
            if (!isPresentationActive() || this.#host.data.getCurrentConversation() !== conversation || this.#conversationId !== conversationId) {
                return true;
            }
            try {
                this.#host.workflow.updateConversationWorkspacePathConfig(conversationId, config);
                this.rebase(config);
                return true;
            } catch (error) {
                this.#retainStaleProjection(config.workspacePath, config);
                errorHandler.warn('ChatConversationSettings', 'Workspace path projection requires refresh', ensureError(error));
                return false;
            }
        };
    }

    #retainStaleProjection(workspacePath: string | null, config: ConversationWorkspacePathConfig | null): void {
        if (config) this.#baseline = { ...config, workspacePath };
        this.#workingOverride = workspacePath;
        this.#derivedProjectionStale = true;
        this.#onDirtyStateChange(true);
        try {
            this.#applyWorkingToUI();
        } catch (presentationError) {
            errorHandler.warn('ChatConversationSettings', 'Workspace path stale-state presentation failed', ensureError(presentationError));
        }
    }

    #updateStatusText(statusElement: HTMLElement, detailText: string): void {
        this.#host.view.updateText(statusElement, `${i18n.t('chat.configuration.filesFolder.description')} ${detailText}`);
    }

    #applyWorkingToUI(): void {
        const config = this.#baseline;
        const dirty = this.isDirty();
        const changeButton = resolveWorkspacePathChangeButton(this.#modal);
        if (changeButton) changeButton.disabled = !Boolean(config);
        const pathElement = resolveWorkspacePathPathElement(this.#modal);
        if (pathElement) {
            const displayed = dirty ? this.#workingOverride : config?.effectiveWorkspacePath;
            pathElement.value = displayed || '/';
            setFieldSurfaceModified(pathElement, dirty);
        }
        const statusElement = resolveWorkspacePathStatusElement(this.#modal);
        if (statusElement) {
            if (!config) this.#updateStatusText(statusElement, i18n.t('chat.configuration.filesFolder.loadingHint'));
            else if (!this.isValid()) this.#updateStatusText(statusElement, i18n.t('chat.configuration.filesFolder.invalidHint'));
            else if (dirty) this.#updateStatusText(statusElement, i18n.t('chat.configuration.filesFolder.stagedHint'));
            else if (this.#derivedProjectionStale) this.#updateStatusText(statusElement, i18n.t('chat.configuration.filesFolder.derivedStaleHint'));
            else if (!config.isValid) this.#updateStatusText(statusElement, resolveWorkspacePathInvalidStatusText(config));
            else if (config.workspacePath) this.#updateStatusText(statusElement, i18n.t('chat.configuration.filesFolder.overrideActiveHint'));
            else this.#updateStatusText(statusElement, i18n.t('chat.configuration.filesFolder.inheritedHint'));
        }
        const resetButton = resolveWorkspacePathResetButton(this.#modal);
        if (resetButton) resetButton.disabled = !Boolean(config && this.#workingOverride);
    }

    async #handleClick(event: Event): Promise<void> {
        const modal = this.#modal;
        const target = event.target;
        if (!modal || !(target instanceof Element)) return;
        const changeButton = resolveWorkspacePathChangeButton(modal);
        if (changeButton && target.closest(`#${changeButton.id}`)) {
            event.preventDefault();
            await this.#openPickerAndStage();
            return;
        }
        const resetButton = resolveWorkspacePathResetButton(modal);
        if (resetButton && target.closest(`#${resetButton.id}`)) {
            event.preventDefault();
            this.#stageOverride(null);
            return;
        }
        const pathElement = resolveWorkspacePathPathElement(modal);
        if (pathElement && changeButton && target.closest(`#${pathElement.id}`)) {
            event.preventDefault();
            await this.#openPickerAndStage();
        }
    }

    async #openPickerAndStage(): Promise<void> {
        const conversation = this.#host.data.getCurrentConversation();
        const config = this.#baseline;
        if (!this.#conversationId || !conversation || conversation.id !== this.#conversationId || !isChatConversationSettingsWritable(conversation)) return;
        if (!config) {
            this.#host.workflow.showNotification(i18n.t('chat.configuration.filesFolder.loadingHint'), 'warning');
            return;
        }
        const access = await resolveWorkspaceBrowserAccess({
            getCurrentUser: () => this.#host.data.api.webui.auth.getMe(),
            scopedBrowserApi: this.#host.data.api.fileExplorer,
            adminBrowserApi: this.#host.data.api.webui.users.workspaceBrowser
        });
        if (!this.#isCurrentConversation()) return;
        const initialPath = this.#workingOverride ?? config.effectiveWorkspacePath;
        const pickerOptions = {
            api: access.browserApi,
            title: i18n.t('chat.configuration.filesFolder.pickerTitle'),
            message: i18n.t('chat.configuration.filesFolder.pickerMessage'),
            labels: buildFolderPickerLabels({ chooseCurrent: i18n.t('common.save') }),
            allowManualPathEntry: true,
            allowManualAbsoluteSelectionOutsideRoot: access.allowManualAbsoluteSelectionOutsideRoot,
            ...(initialPath && isAbsoluteOsPath(initialPath) ? { initialAbsolutePathToBrowse: initialPath } : {}),
            ...(initialPath && !isAbsoluteOsPath(initialPath) ? { initialVirtualPath: initialPath } : {})
        };
        const result = await showFolderPickerModal(pickerOptions);
        if (!result || !this.#isCurrentConversation()) return;
        this.#stagePickerResult(result);
    }

    #stagePickerResult(result: FolderPickerResult): void {
        if (result.resultType !== 'selected') return;
        const nextValue = resolveFolderPickerPathOverride(result);
        if (nextValue === undefined) {
            this.#host.workflow.showNotification(i18n.t('chat.configuration.filesFolder.invalidHint'), 'error');
            return;
        }
        this.#stageOverride(nextValue);
    }

    #stageOverride(nextOverride: string | null): void {
        this.#workingOverride = nextOverride;
        this.refreshWorkingPresentation();
    }

    #isCurrentConversation(): boolean {
        const conversation = this.#host.data.getCurrentConversation();
        return Boolean(this.#conversationId && conversation?.id === this.#conversationId && isChatConversationSettingsWritable(conversation));
    }
}

export { ConversationWorkspacePathSettingsController };
