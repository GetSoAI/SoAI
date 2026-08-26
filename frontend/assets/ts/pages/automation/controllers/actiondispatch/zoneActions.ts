/* SoAI - Automation page zone actions [frontend/assets/ts/pages/automation/controllers/actiondispatch/zoneActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { normalizeConversationId } from '@features/chat/public.ts';
import { resolveAutomationZoneByKey } from '@pages/automation/contracts/zoneKey.ts';
import type { AutomationPageActionDispatcherHost } from '@pages/automation/controllers/actiondispatch/AutomationPageActionDispatcherHost.ts';
import { refreshAutomationDataOrNotify } from '@pages/automation/controllers/actiondispatch/navigationActions.ts';
import { applyZoneSelection } from '@pages/automation/controllers/stateTransitions.ts';

const refreshWithNotification = async (host: AutomationPageActionDispatcherHost): Promise<void> => {
    await refreshAutomationDataOrNotify(host, { logSource: 'AutomationZoneActions', logMessage: 'Refresh failed after selecting zone' });
};

const handleSelectZone = (host: AutomationPageActionDispatcherHost, zoneKey: string | null): void => {
    const state = host.state.getState();
    const selectedZone = zoneKey ? resolveAutomationZoneByKey(state.zones, zoneKey) : null;
    const { state: nextState, requiresWindowRefresh } = applyZoneSelection(state, zoneKey);
    host.state.setState(nextState);
    const occurrenceModal = host.controllers.getOccurrenceModal();
    if (!zoneKey) {
        occurrenceModal?.close();
    } else if (selectedZone) {
        const conversationId = normalizeConversationId(selectedZone.convId);
        if (conversationId) {
            occurrenceModal?.close();
            host.state.navigateToConversation(conversationId);
            return;
        }
        host.controllers.run('automation:occurrence:open', async () => {
            host.controllers.getOccurrenceModal()?.open(selectedZone, nextState.calendarSettings);
        });
    }
    if (requiresWindowRefresh) {
        host.controllers.requestCenterPeriodAfterNextRender();
        host.controllers.run('automation:selectZone:refreshWindow', async () => refreshWithNotification(host));
        return;
    }
    host.state.queueRender();
};

export { handleSelectZone };
