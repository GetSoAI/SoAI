/* SoAI - Automation page action dispatcher host [frontend/assets/ts/pages/automation/controllers/actiondispatch/AutomationPageActionDispatcherHost.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { NotificationType } from '@core/ui/notifications/types.ts';
import type { AutomationCalendarSettingsController } from '@pages/automation/controllers/AutomationCalendarSettingsController.ts';
import type { AutomationEditorController } from '@pages/automation/controllers/AutomationEditorController.ts';
import type { AutomationOccurrenceModalController } from '@pages/automation/controllers/AutomationOccurrenceModalController.ts';
import type { AutomationDataService } from '@features/automation/public.ts';
import type { AutomationPageState, AutomationUiRefs } from '@pages/automation/types.ts';

interface AutomationActionStatePort {
    ui: AutomationUiRefs;
    dataService: AutomationDataService;
    getState(): AutomationPageState;
    setState(next: AutomationPageState): void;
    persistPreferences(): void;
    queueRender(): void;
    refreshData(): Promise<void>;
    stageCalendarTransition(direction: 'detail-forward' | 'detail-backward', windowSignature: string, variant?: 'standard' | 'slow'): void;
    setTimeout(callback: () => void, delay: number): number | null;
    showNotification(message: string, type?: NotificationType): void;
    navigateToConversation(conversationId: string): void;
}

interface AutomationActionControllerPort {
    getEditor(): AutomationEditorController | null;
    getCalendarSettings(): AutomationCalendarSettingsController | null;
    getOccurrenceModal(): AutomationOccurrenceModalController | null;
    requestCenterPeriodAfterNextRender(): void;
    requestCenterNowLineAfterNextRender(): void;
    centerNowLineNow(): void;
    animateVisiblePeriod(direction: -1 | 1): Promise<void>;
    run(operation: string, task: () => Promise<void> | void): void;
    isPreferencesCorrupt(): boolean;
    resetPreferences(): void;
}

interface AutomationWindowRunActions {
    enterWindowRunsSelectMode(): void;
    exitWindowRunsSelectMode(): void;
    toggleWindowRunsOccurrenceSelected(zoneKey: string): void;
    batchDeleteWindowRunsOccurrences(): void;
    deleteWindowRunsOccurrence(zoneKey: string): void;
}

interface AutomationPageActionDispatcherHost {
    state: AutomationActionStatePort;
    controllers: AutomationActionControllerPort;
    windowRuns: AutomationWindowRunActions;
}

export type { AutomationPageActionDispatcherHost };
