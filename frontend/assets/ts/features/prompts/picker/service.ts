/* SoAI - Prompts picker stream subscription [frontend/assets/ts/features/prompts/picker/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { PROMPTS } from '@core/realtime/streammanager/resources/ids.ts';
import type { PromptsPickerStreamManager, PromptSnapshot } from '@features/prompts/picker/types.ts';

interface PromptsPickerStreamSubscriptionOptions {
    manager: PromptsPickerStreamManager;
    signal: AbortSignal;
    session: number;
    setUnsubscribe(unsubscribe: () => void): void;
    isActive(session: number): boolean;
    applyPayload(value: JsonValue): void;
    handleError(error: Error, message: string): void;
    finishLoading(session: number): void;
}

const applyPromptsSnapshot = (options: PromptsPickerStreamSubscriptionOptions, snapshot: PromptSnapshot): void => {
    if (!options.isActive(options.session)) {
        return;
    }
    if (snapshot.status === 'error') {
        options.handleError(ensureError(snapshot.error ?? new Error('Prompts stream failed')), i18n.t('prompts.picker.loadFailed'));
        return;
    }
    if (snapshot.value === null) {
        return;
    }
    try {
        options.applyPayload(snapshot.value);
    } catch (error) {
        const runtimeError = ensureError(error);
        options.handleError(runtimeError, i18n.t('prompts.picker.loadFailed'));
    }
};

const startPromptsPickerStream = async (options: PromptsPickerStreamSubscriptionOptions): Promise<void> => {
    const unsubscribe = options.manager.subscriptions.subscribeResourceState(PROMPTS, (snapshot: PromptSnapshot): void => applyPromptsSnapshot(options, snapshot), { immediate: true, ensureStart: false });
    options.setUnsubscribe(unsubscribe);
    try {
        const value = await options.manager.resources.ensureResourceStarted(PROMPTS, { signal: options.signal });
        if (options.isActive(options.session) && value !== null) {
            options.applyPayload(value);
        }
    } catch (error) {
        const runtimeError = ensureError(error);
        if (options.isActive(options.session)) options.handleError(runtimeError, i18n.t('prompts.picker.loadFailed'));
    } finally {
        options.finishLoading(options.session);
    }
};

export { startPromptsPickerStream };
