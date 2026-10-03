/* SoAI - Chat completion execution eligibility for model catalog entries [frontend/assets/ts/core/models/chatExecutionEligibility.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isLocalModelCatalogEntry, type ModelCatalogEntry } from '@core/api/contracts/modelCatalogContracts.ts';
import { supportsOpenAIEndpointForEntry } from '@core/openai/capabilityChecks.ts';

type ChatExecutionIneligibilityReason = 'disabled' | 'unavailable' | 'unsupported';

interface ChatExecutionEligibility {
    eligible: boolean;
    reason: ChatExecutionIneligibilityReason | null;
}

const CHAT_EXECUTION_ENDPOINT = 'chat_completions';

const ineligible = (reason: ChatExecutionIneligibilityReason): ChatExecutionEligibility => ({ eligible: false, reason });

const resolveChatExecutionEligibility = (entry: ModelCatalogEntry): ChatExecutionEligibility => {
    if (!entry.isEnabled) {
        return ineligible('disabled');
    }
    if (isLocalModelCatalogEntry(entry) && (entry.status.toLowerCase() !== 'active' || entry.isOrphaned || !(entry.isLoaded || entry.isAvailable))) {
        return ineligible('unavailable');
    }
    if (!supportsOpenAIEndpointForEntry(entry, CHAT_EXECUTION_ENDPOINT)) {
        return ineligible('unsupported');
    }
    return { eligible: true, reason: null };
};

export { resolveChatExecutionEligibility };
export type { ChatExecutionEligibility, ChatExecutionIneligibilityReason };
