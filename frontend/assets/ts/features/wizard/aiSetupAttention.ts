/* SoAI - Wizard feature AI setup attention notifications [frontend/assets/ts/features/wizard/aiSetupAttention.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AiSetupAttentionLifecycleContract } from '@core/aisetup/protocols.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { onNavigationComplete } from '@core/navigationEvents.ts';
import { buildAiSetupResumeRoute } from '@core/routing/router/aiSetupRoutes.ts';
import { AUTH_ROUTE_WIZARD } from '@core/routing/router/authRouteTarget.ts';
import { listAiSetupItemsNeedingAttention } from '@core/storage/aisetup/aiSetupAttention.ts';
import type { AiSetupState } from '@core/storage/aisetup/aiSetupTypes.ts';
import type { AiSetupStateUpdate } from '@core/storage/service/aiSetupActions.ts';
import type { TaskOperationsApi } from '@core/tasks/protocols.ts';
import { dismissPersistentNotificationsByDedupeKey, showPersistentNotification } from '@core/ui/notifications/notifications.ts';

const AI_SETUP_ATTENTION_DEDUPE_KEY = 'ai-setup-pending';

interface AiSetupAttentionDependencies {
    storage: {
        getAiSetup(): AiSetupState | null;
        updateAiSetup(update: AiSetupStateUpdate): AiSetupState | null;
        isWizardCompletionPending(): boolean;
    };
    taskOperations: Pick<TaskOperationsApi, 'getOperations' | 'subscribeOperations' | 'reconcileOperations'>;
    router: {
        getCurrentRoute(): string | null;
        navigate(route: string): Promise<void>;
    };
}

class AiSetupAttentionService implements AiSetupAttentionLifecycleContract {
    readonly #dependencies: AiSetupAttentionDependencies;
    #generation = 0;
    #unsubscribe: (() => void) | null = null;
    #unsubscribeNavigation: (() => void) | null = null;

    constructor(dependencies: AiSetupAttentionDependencies) {
        this.#dependencies = dependencies;
    }

    initialize(): void {
        this.dispose();
        void this.#start(this.#generation).catch((error) => errorHandler.error('AiSetupAttention', 'AI setup attention could not start', ensureError(error)));
    }

    dispose(): void {
        this.#generation += 1;
        this.#unsubscribe?.();
        this.#unsubscribe = null;
        this.#unsubscribeNavigation?.();
        this.#unsubscribeNavigation = null;
        dismissPersistentNotificationsByDedupeKey([AI_SETUP_ATTENTION_DEDUPE_KEY]);
    }

    async #start(generation: number): Promise<void> {
        try {
            await this.#dependencies.taskOperations.reconcileOperations();
        } catch (error) {
            errorHandler.warn('AiSetupAttention', 'Task operations could not be reconciled; AI setup attention is paused for this session', ensureError(error));
            return;
        }
        if (generation !== this.#generation) return;
        this.#unsubscribe = this.#dependencies.taskOperations.subscribeOperations({}, () => this.#evaluate());
        this.#unsubscribeNavigation = onNavigationComplete(() => this.#evaluate());
        this.#evaluate();
    }

    #evaluate(): void {
        const { storage, taskOperations, router } = this.#dependencies;
        if (storage.isWizardCompletionPending() || router.getCurrentRoute()?.startsWith(AUTH_ROUTE_WIZARD) === true) return;
        const activeTaskIds = new Set(taskOperations.getOperations().map((operation) => operation.id));
        const itemIds = listAiSetupItemsNeedingAttention(storage.getAiSetup(), activeTaskIds);
        if (itemIds.length === 0) return;
        storage.updateAiSetup((current) => (current === null ? null : { ...current, pendingToastShownFor: [...new Set([...current.pendingToastShownFor, ...itemIds])] }));
        showPersistentNotification({
            message: i18n.t('wizard.aiSetup.resume.toast'),
            type: 'warning',
            dedupeKey: AI_SETUP_ATTENTION_DEDUPE_KEY,
            buttons: [
                {
                    text: i18n.t('wizard.aiSetup.resume.link'),
                    variant: 'warning',
                    action: async (): Promise<boolean> => {
                        await router.navigate(buildAiSetupResumeRoute());
                        return true;
                    }
                }
            ]
        });
    }
}

export { AI_SETUP_ATTENTION_DEDUPE_KEY, AiSetupAttentionService };
export type { AiSetupAttentionDependencies };
