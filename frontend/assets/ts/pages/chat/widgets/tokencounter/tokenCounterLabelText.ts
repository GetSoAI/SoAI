/* SoAI - Chat token counter label text [frontend/assets/ts/pages/chat/widgets/tokencounter/tokenCounterLabelText.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { resolveTokenUsageVisibleContextWindowTokens, tokenUsageHasEstimatedContextWindow, tokenUsageHasEstimatedCurrentTokens, type TokenUsageSnapshot } from '@core/api/contracts/tokenUsageContracts.ts';
import { formatInvariantNumber } from '@core/localization/public.ts';
import { readNonNegativeFiniteNumberOrNullValue } from '@core/types/payloadNumberReaders.ts';
import type { TokenCounterMode } from '@pages/chat/widgets/tokencounter/contracts.ts';

interface TokenCounterLabelTextOptions {
    enabled: boolean;
    mode: TokenCounterMode;
    usage: TokenUsageSnapshot | null;
    tokensPerSecond: number | null;
}

const resolveTokenCounterLabelText = (options: TokenCounterLabelTextOptions): string => {
    if (!options.enabled || options.mode === 'inactive') {
        return i18n.t('chat.tokenCounter.inactive');
    }

    if (options.mode === 'rate') {
        const unit = i18n.t('chat.tokenCounter.unitTokensPerSecond');
        const rateUnavailable = i18n.t('chat.tokenCounter.rateUnavailable');
        const rate = readNonNegativeFiniteNumberOrNullValue(options.tokensPerSecond);
        if (rate === null) {
            return `${rateUnavailable} ${unit}`;
        }
        return `${formatInvariantNumber(rate, { maximumFractionDigits: 1 })} ${unit}`;
    }

    const unit = i18n.t('chat.tokenCounter.unitTokens');
    const rateUnavailable = i18n.t('chat.tokenCounter.rateUnavailable');
    const usage = options.usage;
    if (!usage) {
        return `${rateUnavailable} ${unit}`;
    }
    const estimatedPrefix = i18n.t('chat.tokenCounter.estimatedPrefix');
    const currentPrefix = tokenUsageHasEstimatedCurrentTokens(usage) ? estimatedPrefix : '';
    const contextWindowPrefix = tokenUsageHasEstimatedContextWindow(usage) ? estimatedPrefix : '';
    const contextWindow = resolveTokenUsageVisibleContextWindowTokens(usage);
    if (contextWindow !== null) {
        return `${currentPrefix}${usage.contextOccupancyTokens}/${contextWindowPrefix}${contextWindow} ${unit}`;
    }
    return `${currentPrefix}${usage.contextOccupancyTokens} ${unit}`;
};

export { resolveTokenCounterLabelText };
