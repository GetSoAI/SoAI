/* SoAI - Chat page token counter view model [frontend/assets/ts/pages/chat/widgets/tokencounter/tokenCounterViewModel.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveTokenUsageVisibleContextWindowTokens, type TokenUsageSnapshot } from '@core/api/contracts/tokenUsageContracts.ts';
import type { TokenCounterMode } from '@pages/chat/widgets/tokencounter/contracts.ts';
import { resolveTokenCounterLabelText } from '@pages/chat/widgets/tokencounter/tokenCounterLabelText.ts';

type TokenCounterSeverity = 'none' | 'warning' | 'critical';

const WARNING_RATIO = 0.85;
const CRITICAL_RATIO = 0.95;

const resolveSeverity = (options: { enabled: boolean; mode: TokenCounterMode; usage: TokenUsageSnapshot | null }): TokenCounterSeverity => {
    if (!options.enabled || options.mode !== 'tokens' || !options.usage) {
        return 'none';
    }
    if (options.usage.promptTokensCapped) {
        return 'critical';
    }
    const limitTokens = resolveTokenUsageVisibleContextWindowTokens(options.usage);
    if (limitTokens === null || limitTokens <= 0) {
        return 'none';
    }
    const ratio = options.usage.contextOccupancyTokens / limitTokens;
    if (ratio >= CRITICAL_RATIO) {
        return 'critical';
    }
    if (ratio >= WARNING_RATIO) {
        return 'warning';
    }
    return 'none';
};

const resolveTokenCounterViewModel = (options: { enabled: boolean; mode: TokenCounterMode; usage: TokenUsageSnapshot | null; tokensPerSecond: number | null }): { labelText: string; isActive: boolean; severity: TokenCounterSeverity } => {
    const isActive = options.enabled && options.mode !== 'inactive';
    return {
        labelText: resolveTokenCounterLabelText(options),
        isActive,
        severity: resolveSeverity(options)
    };
};

export { resolveTokenCounterViewModel };
export type { TokenCounterSeverity };
