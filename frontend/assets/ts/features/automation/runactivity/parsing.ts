/* SoAI - Automation feature parsing [frontend/assets/ts/features/automation/runactivity/parsing.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isAutomationRunStatus } from '@core/automation/guards.ts';
import { readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import type { AutomationRunStatus } from '@features/automation/runactivity/types.ts';

interface AutomationRunRecord {
    runId: string;
    automationId: string;
    status: AutomationRunStatus;
}

const parseRunStatusFromRecord = (record: { runId: string; automationId: string; status: string }): AutomationRunRecord => {
    const runId = readRequiredTrimmedStringValue(record.runId, 'Automation run record.runId');
    const automationId = readRequiredTrimmedStringValue(record.automationId, 'Automation run record.automationId');
    const statusValue = record.status;
    if (!isAutomationRunStatus(statusValue)) {
        throw new Error(`Automation run record.status is invalid: ${String(statusValue)}`);
    }
    return { runId, automationId, status: statusValue };
};

export { parseRunStatusFromRecord };
export type { AutomationRunRecord };
