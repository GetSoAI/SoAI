/* SoAI - Prompts page service [frontend/assets/ts/pages/prompts/controllers/page/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { isFunction, isString } from '@core/typeGuards.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { requireContentPreviewModalService } from '@core/ui/modals/contentpreview/service.ts';
import type { PromptsApiClient } from '@pages/prompts/contracts/promptsTypes.ts';
import { isDraftPromptId, setupUnsavedChangesGuard, type PromptsPageActionsHost } from '@pages/prompts/controllers/page/effects.ts';
import { requirePromptsUi } from '@pages/prompts/dom.ts';
import type { PromptsRuntimeContext } from '@pages/prompts/controllers/page/contracts.ts';

type PromptsPageServiceHost = PromptsRuntimeContext;

interface PromptsCollectionShellLayout {
    grid: HTMLElement;
    emptyState: HTMLElement | null;
}

const requirePromptsApi = (host: PromptsPageServiceHost): PromptsApiClient => {
    if (!host.state.promptsApi) {
        throw new Error('Prompts API is not available');
    }
    return host.state.promptsApi;
};

const requirePromptsCardController = (host: PromptsPageServiceHost): NonNullable<PromptsPageServiceHost['state']['cardController']> => {
    if (!host.state.cardController) {
        throw new Error('Prompts card controller is not available');
    }
    return host.state.cardController;
};

const loadData = async (host: PromptsPageServiceHost): Promise<void> => {
    const cardController = requirePromptsCardController(host);
    cardController.showLoading();
    await host.owners.collectionLifecycle.withLoading(
        async (): Promise<true> => {
            await host.operations.ensureDataAdapterReady();
            host.operations.reapplyCollection();
            await host.owners.collections.ensureStream({ allowDiscovery: true });
            return true;
        },
        {
            onSuccess: async () => {
                cardController.setDataInitialized();
                await host.owners.streaming.ensureSubscriptions();
            }
        }
    );
};

const beforePageInitialize = async (host: PromptsPageServiceHost, parameters: JsonObject | null): Promise<void> => {
    void parameters;
    host.controls.setSearchQuery('');
    host.state.promptsApi = host.owners.api.webui.prompts;
    const required: Array<keyof PromptsApiClient> = ['list', 'create', 'get', 'update', 'delete', 'batchDelete'];
    if (!host.state.promptsApi || required.some((key) => !isFunction(host.state.promptsApi?.[key]))) {
        throw new Error('Prompts API is not available');
    }
};

const onCollectionShellReady = async (host: PromptsPageServiceHost & PromptsPageActionsHost, _parameters: JsonObject | null, _layout: PromptsCollectionShellLayout): Promise<void> => {
    const promptsUi = requirePromptsUi({
        requireHTMLElement: (selector, context) => host.owners.pageDom.requireHTMLElement(selector, context),
        optionalHTMLElement: (selector, context) => host.owners.pageDom.optionalHTMLElement(selector, context)
    });
    host.state.ui = promptsUi;
    host.components.selectionController.bindUi(host.state.ui);
    const selectedCard = host.state.ui.selectedPromptsCard;
    host.owners.pageDom.toggleClass(selectedCard, 'u-hidden', true);
    host.owners.pageDom.updateAttribute(selectedCard, 'aria-hidden', 'true');
    host.operations.renderItems();
    host.components.selectionController.refreshUI();
    host.components.promptEnhancer.setupEventListeners();
    setupUnsavedChangesGuard(host);
    terminateHandledPromise(host.owners.pageLifecycle.run('prompts:promptEnhancer:reloadModels', () => host.components.promptEnhancer.reloadModelCatalog()));
};

const deletePrompt = async (host: PromptsPageServiceHost, promptId: string): Promise<void> => {
    await host.owners.pageLifecycle.run('prompts:deletePrompt', async () => {
        const normalizedId = String(promptId ?? '').trim();
        if (!normalizedId) {
            return;
        }
        if (isDraftPromptId(normalizedId)) {
            host.state.draftPromptId = null;
            host.state.editingPromptId = null;
            host.operations.removeItemById(normalizedId);
            host.operations.reapplyCollection({ shouldRender: true, updateStats: true, updateFilters: false });
            return;
        }
        const deleted = await host.owners.streaming.runTask('prompts.deleteSingle', () => requirePromptsApi(host).delete(normalizedId), {
            displayName: i18n.t('prompts.actions.deletePrompt'),
            rethrow: false
        });
        if (deleted !== null) {
            host.operations.removeItemById(normalizedId);
            host.owners.feedback.show(i18n.t('prompts.notifications.promptDeleted'), 'success');
        }
    });
};

const deleteSelectedPrompts = async (host: PromptsPageServiceHost, promptIds: readonly (string | number)[]): Promise<void> => {
    await host.owners.pageLifecycle.run('prompts:deleteSelectedPrompts', async () => {
        const ids = promptIds.map((id) => String(id)).filter((value) => value.trim().length > 0);
        if (!ids.length) {
            return;
        }
        const deleted = await host.owners.streaming.runTask('prompts.deleteMultiple', () => requirePromptsApi(host).batchDelete(ids), {
            displayName: i18n.t('prompts.actions.deleteSelected'),
            successMessage: i18n.t('prompts.notifications.promptsDeleted'),
            rethrow: false
        });
        if (deleted !== null) {
            ids.forEach((id) => host.operations.removeItemById(id));
            host.components.selectionController.clear();
            if (host.components.selectionController.isActive()) {
                host.components.selectionController.toggleMode();
            }
        }
    });
};

const savePromptFromModal = async (host: PromptsPageServiceHost, options: { silent?: boolean } = {}): Promise<boolean> => {
    try {
        void options;
        await requireContentPreviewModalService().requestSave();
        return true;
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.error('PromptsPage', 'Modal prompt save failed', runtimeError);
        host.owners.feedback.show(i18n.t('prompts.notifications.saveFailed'), 'error');
        throw runtimeError;
    }
};

const copyPromptContent = async (host: PromptsPageServiceHost, content: string | null | undefined): Promise<void> => {
    await host.owners.pageLifecycle.run('prompts:copyContent', async () => {
        const raw = isString(content) ? content : '';
        if (raw.length === 0) {
            host.owners.feedback.show(i18n.t('prompts.notifications.emptyPromptCopy'), 'warning');
            return;
        }
        await host.owners.services.copyToClipboard(raw, {
            notify: (_message: string, type: string) => {
                if (type === 'copy') {
                    host.owners.feedback.show(i18n.t('prompts.notifications.promptCopied'), 'copy');
                    return;
                }
                host.owners.feedback.show(i18n.t('prompts.notifications.copyFailed'), 'error');
            }
        });
    });
};

const onDestroy = async (host: PromptsPageServiceHost): Promise<void> => {
    host.state.ui = null;
    host.state.unsavedChangesGuardCleanup?.();
    host.state.unsavedChangesGuardCleanup = null;
    host.components.promptEnhancer.dispose();
    requirePromptsCardController(host).dispose();
};

export { beforePageInitialize, copyPromptContent, deletePrompt, deleteSelectedPrompts, loadData, onCollectionShellReady, onDestroy, savePromptFromModal };
export type { PromptsPageServiceHost };
