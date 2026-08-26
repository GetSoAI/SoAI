/* SoAI - Automation initial run selection resolution [frontend/assets/ts/pages/automation/services/AutomationInitialRunSelectionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { normalizeConversationId } from '@features/chat/public.ts';
import { buildAutomationZoneKey } from '@pages/automation/contracts/zoneKey.ts';
import type { AutomationDataService } from '@features/automation/public.ts';
import type { AutomationInitialSelection } from '@pages/automation/types.ts';

const AutomationInitialRunSelectionController = async (dependencies: { dataService: AutomationDataService; runId: string | null; abortSignal: AbortSignal | null }): Promise<AutomationInitialSelection | null> => {
    if (!dependencies.runId) {
        return null;
    }
    const run = await dependencies.dataService.getRun(dependencies.runId);
    if (dependencies.abortSignal?.aborted || normalizeConversationId(run.convId)) {
        return null;
    }
    return {
        focusDateUtcMs: run.scheduledAtMs,
        selectedDateUtcMs: run.scheduledAtMs,
        selectedZoneKey: buildAutomationZoneKey(run.automationId, run.scheduledAtMs)
    };
};

export { AutomationInitialRunSelectionController };
