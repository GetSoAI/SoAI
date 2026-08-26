/* SoAI - Chat page token counter rendering [frontend/assets/ts/pages/chat/widgets/tokencounter/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TokenUsageSnapshot } from '@core/api/contracts/tokenUsageContracts.ts';
import { i18n } from '@core/i18n/index.ts';
import { resolveTokenCounterErrorNotificationMessage } from '@features/chat/public.ts';
import { resolveTokenCounterViewModel } from '@pages/chat/widgets/tokencounter/tokenCounterViewModel.ts';
import type { TokenCounterHost, TokenCounterMode } from '@pages/chat/widgets/tokencounter/contracts.ts';
import type { TokenCounterUsageRateTracker } from '@pages/chat/widgets/tokencounter/tokenCounterUsageRateTracker.ts';
import type { ChatTokenCountErrorEvent } from '@core/realtime/eventcontracts/chatControlContracts.ts';

interface TokenCounterErrorState {
    notificationMessage: string;
    usage: TokenUsageSnapshot | null;
}

const renderTokenCounter = (inputArguments: { host: TokenCounterHost; enabled: boolean; mode: TokenCounterMode; usageTracker: TokenCounterUsageRateTracker }): void => {
    const buttons = inputArguments.host.requireTokenCounterButtons();
    const usage = inputArguments.enabled ? inputArguments.usageTracker.getLastTokenUsage() : null;
    const tokensPerSecond = inputArguments.enabled ? inputArguments.usageTracker.resolveTokensPerSecond() : null;
    const viewModel = resolveTokenCounterViewModel({
        enabled: inputArguments.enabled,
        mode: inputArguments.mode,
        usage,
        tokensPerSecond
    });
    for (const button of buttons) {
        const label = inputArguments.host.requireTokenCounterLabel(button);
        inputArguments.host.pageDom.toggleClass(button, 'is-active', viewModel.isActive);
        inputArguments.host.pageDom.updateAttribute(button, 'aria-pressed', viewModel.isActive ? 'true' : 'false');
        inputArguments.host.pageDom.toggleClass(button, 'is-warning', viewModel.severity === 'warning');
        inputArguments.host.pageDom.toggleClass(button, 'is-critical', viewModel.severity === 'critical');
        inputArguments.host.pageDom.updateText(label, viewModel.labelText);
    }
};

const resolveTokenCounterErrorState = (event: ChatTokenCountErrorEvent): TokenCounterErrorState => {
    const promptBudget = event.promptBudget;
    let message = event.userMessage ?? event.message;
    if (promptBudget?.type === 'prompt_budget_exceeded' && promptBudget.promptTokens !== null) {
        message = i18n.t('chat.notifications.promptBudgetExceeded', { promptTokens: promptBudget.promptTokens, budgetTokens: promptBudget.budgetTokens });
    } else if (promptBudget?.type === 'prompt_budget_capped') {
        message = i18n.t('chat.notifications.promptBudgetCapped', { budgetTokens: promptBudget.budgetTokens });
    }
    return {
        notificationMessage: resolveTokenCounterErrorNotificationMessage(message),
        usage: event.usagePreview
    };
};

export { renderTokenCounter, resolveTokenCounterErrorState };
