/* SoAI - Chat feature conversation settings effects [frontend/assets/ts/features/chat/conversationsettings/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import type { ConversationSettingsSectionStateTransition } from '@features/chat/conversationsettings/actions.ts';
import type { ConversationSettingsSection, ConversationSettingsSectionState } from '@features/chat/conversationsettings/types.ts';

interface ApplyConversationSectionStateOptions<T> {
    baseline: T | null;
    current: T | null;
    hasChanges: (current: T, baseline: T) => boolean;
    isValid?: boolean | undefined;
    section: ConversationSettingsSection;
    sectionState: ConversationSettingsSectionState;
    resolveSectionApplyStateTransition: (inputArguments: { baseline: T | null; current: T | null; hasChanges: (current: T, baseline: T) => boolean; isValid?: boolean | undefined; section: ConversationSettingsSection; sectionState: ConversationSettingsSectionState }) => ConversationSettingsSectionStateTransition;
    setSectionState: (state: ConversationSettingsSectionState) => void;
    syncConfigurationActionState: () => void;
}

interface ApplyConversationSettingsUpdateOptions<T> {
    conversationId: string;
    updateToken: number;
    isUpdateTokenActive: (token: number) => boolean;
    boundary: string;
    updateRequest: () => Promise<T>;
    onSuccess: (payload: T) => void;
    onAcceptedSuccess?: (payload: T) => Promise<void> | void;
    onFinally?: () => void;
    errorMessage: string;
    isStillActive: () => boolean;
    runWithBoundary: (boundary: string, request: () => Promise<T>) => Promise<T>;
    successMessage: string;
    failureMessage: string;
    showNotification: (message: string, type: 'success' | 'error') => void;
}

const applyConversationSectionApplyState = <T>(options: ApplyConversationSectionStateOptions<T>): void => {
    const transition = options.resolveSectionApplyStateTransition({
        baseline: options.baseline,
        current: options.current,
        hasChanges: options.hasChanges,
        isValid: options.isValid,
        section: options.section,
        sectionState: options.sectionState
    });
    if (!transition.changed) {
        return;
    }
    options.setSectionState(transition.state);
    options.syncConfigurationActionState();
};

const applyConversationSettingsUpdate = async <T>(options: ApplyConversationSettingsUpdateOptions<T>): Promise<void> => {
    try {
        const updated = await options.runWithBoundary(options.boundary, options.updateRequest);
        await options.onAcceptedSuccess?.(updated);
        if (!options.isStillActive() || !options.isUpdateTokenActive(options.updateToken)) {
            return;
        }
        options.onSuccess(updated);
    } catch (error) {
        const runtimeError = ensureError(error);
        throw runtimeError;
    } finally {
        if (options.isStillActive() && options.isUpdateTokenActive(options.updateToken)) {
            options.onFinally?.();
        }
    }
};

export { applyConversationSectionApplyState, applyConversationSettingsUpdate };
export type { ApplyConversationSectionStateOptions, ApplyConversationSettingsUpdateOptions };
