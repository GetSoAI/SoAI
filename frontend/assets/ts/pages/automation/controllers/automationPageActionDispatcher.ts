/* SoAI - Automation page action dispatcher [frontend/assets/ts/pages/automation/controllers/automationPageActionDispatcher.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import {
    AUTOMATION_ACTION_ADD_TURN,
    AUTOMATION_ACTION_CYCLE_VIEW,
    AUTOMATION_ACTION_DELETE_AUTOMATION,
    AUTOMATION_ACTION_EDIT_AUTOMATION,
    AUTOMATION_ACTION_MODAL_EDIT,
    AUTOMATION_ACTION_MCP_SERVER_TOGGLE,
    AUTOMATION_ACTION_MCP_TOOL_GROUP_TOGGLE,
    AUTOMATION_ACTION_MCP_TOOL_SEARCH,
    AUTOMATION_ACTION_MCP_TOOL_TOGGLE,
    AUTOMATION_ACTION_NAV_NEXT,
    AUTOMATION_ACTION_NAV_PREVIOUS,
    AUTOMATION_ACTION_NAV_TODAY,
    AUTOMATION_ACTION_OPEN_CALENDAR_SETTINGS_MODAL,
    AUTOMATION_ACTION_OPEN_CHAT_TRANSCRIPT,
    AUTOMATION_ACTION_OPEN_CREATE_MODAL,
    AUTOMATION_ACTION_OPEN_FOLDER_MODAL,
    AUTOMATION_ACTION_OPEN_PARAMETERS_MODAL,
    AUTOMATION_ACTION_REGISTRY_NEXT,
    AUTOMATION_ACTION_REGISTRY_PREVIOUS,
    AUTOMATION_ACTION_PREVIEW_AUTOMATION,
    AUTOMATION_ACTION_REMOVE_TURN,
    AUTOMATION_ACTION_RESET_PREFERENCES,
    AUTOMATION_ACTION_SAVE_AUTOMATION,
    AUTOMATION_ACTION_SAVE_CALENDAR_SETTINGS,
    AUTOMATION_ACTION_SELECT_DAY,
    AUTOMATION_ACTION_SELECT_ZONE,
    AUTOMATION_ACTION_SET_VIEW,
    AUTOMATION_ACTION_TIME_GRID_CREATE_AT,
    AUTOMATION_ACTION_TOGGLE_AUTOMATION_ENABLED,
    AUTOMATION_ACTION_TOGGLE_REGISTRY_OVERLAY,
    AUTOMATION_ACTION_WINDOW_RUNS_BATCH_DELETE,
    AUTOMATION_ACTION_WINDOW_RUNS_DELETE_OCCURRENCE,
    AUTOMATION_ACTION_WINDOW_RUNS_ENTER_SELECT_MODE,
    AUTOMATION_ACTION_WINDOW_RUNS_EXIT_SELECT_MODE,
    AUTOMATION_ACTION_WINDOW_RUNS_TOGGLE_SELECTED,
    type AutomationActionId
} from '@features/automation/public.ts';
import type { AutomationPageActionDispatcherHost } from '@pages/automation/controllers/actiondispatch/AutomationPageActionDispatcherHost.ts';
import { handleAddTurn, handleEnterEditMode, handleOpenCalendarSettings, handleOpenCreate, handleOpenParametersModal, handleOpenWorkspaceModal, handleRemoveTurn, handleSaveAutomation, handleSaveCalendarSettings } from '@pages/automation/controllers/actiondispatch/modalActions.ts';
import { handleCycleViewMode, handleNavigate, handleNavigateRegistryPage, handleNavigateToday, handleSelectDay, handleSetViewMode, handleToggleRegistryOverlay } from '@pages/automation/controllers/actiondispatch/navigationActions.ts';
import { handleResetPreferences } from '@pages/automation/controllers/actiondispatch/preferencesActions.ts';
import { handleOpenChatTranscript } from '@pages/automation/controllers/actiondispatch/transcriptActions.ts';
import { handleSelectZone } from '@pages/automation/controllers/actiondispatch/zoneActions.ts';
import { handleDeleteAutomation, handleEditAutomation, handlePreviewAutomation, handleToggleAutomationEnabled } from '@pages/automation/controllers/automationCrudActions.ts';
import { requireAutomationId } from '@pages/automation/controllers/automationManagementActions.ts';

const requireZoneKey = (element: HTMLElement, label: string): string => {
    const value = (element.dataset['zoneKey'] ?? '').trim();
    if (!value) {
        throw new Error(`${label} requires a zoneKey`);
    }
    return value;
};

const dispatchAutomationPageAction = (host: AutomationPageActionDispatcherHost, actionId: AutomationActionId, element: HTMLElement): void => {
    if (actionId !== AUTOMATION_ACTION_RESET_PREFERENCES && host.controllers.isPreferencesCorrupt()) {
        throw new Error('Automation preferences are corrupt; reset is required');
    }
    switch (actionId) {
        case AUTOMATION_ACTION_MCP_SERVER_TOGGLE:
        case AUTOMATION_ACTION_MCP_TOOL_GROUP_TOGGLE:
        case AUTOMATION_ACTION_MCP_TOOL_SEARCH:
        case AUTOMATION_ACTION_MCP_TOOL_TOGGLE:
            return;
        case AUTOMATION_ACTION_NAV_PREVIOUS:
            handleNavigate(host, -1);
            return;
        case AUTOMATION_ACTION_NAV_NEXT:
            handleNavigate(host, 1);
            return;
        case AUTOMATION_ACTION_NAV_TODAY:
            handleNavigateToday(host);
            return;
        case AUTOMATION_ACTION_SET_VIEW:
            handleSetViewMode(host, element.dataset['view'] ?? '');
            return;
        case AUTOMATION_ACTION_CYCLE_VIEW:
            handleCycleViewMode(host);
            return;
        case AUTOMATION_ACTION_SELECT_DAY:
            handleSelectDay(host, element.dataset['date'] ?? '');
            return;
        case AUTOMATION_ACTION_SELECT_ZONE:
            handleSelectZone(host, element.dataset['zoneKey'] ?? null);
            return;
        case AUTOMATION_ACTION_TIME_GRID_CREATE_AT:
            return;
        case AUTOMATION_ACTION_OPEN_CREATE_MODAL:
            handleOpenCreate(host);
            return;
        case AUTOMATION_ACTION_REGISTRY_PREVIOUS:
            handleNavigateRegistryPage(host, -1);
            return;
        case AUTOMATION_ACTION_REGISTRY_NEXT:
            handleNavigateRegistryPage(host, 1);
            return;
        case AUTOMATION_ACTION_EDIT_AUTOMATION: {
            const automationId = requireAutomationId(element, 'Edit automation');
            handleEditAutomation(host, automationId);
            return;
        }
        case AUTOMATION_ACTION_PREVIEW_AUTOMATION: {
            const automationId = requireAutomationId(element, 'Preview automation');
            handlePreviewAutomation(host, automationId);
            return;
        }
        case AUTOMATION_ACTION_TOGGLE_AUTOMATION_ENABLED: {
            const automationId = requireAutomationId(element, 'Toggle automation');
            handleToggleAutomationEnabled(host, element, automationId);
            return;
        }
        case AUTOMATION_ACTION_DELETE_AUTOMATION: {
            const automationId = requireAutomationId(element, 'Delete automation');
            handleDeleteAutomation(host, automationId);
            return;
        }
        case AUTOMATION_ACTION_OPEN_CALENDAR_SETTINGS_MODAL:
            handleOpenCalendarSettings(host);
            return;
        case AUTOMATION_ACTION_TOGGLE_REGISTRY_OVERLAY:
            handleToggleRegistryOverlay(host);
            return;
        case AUTOMATION_ACTION_MODAL_EDIT:
            handleEnterEditMode(host);
            return;
        case AUTOMATION_ACTION_OPEN_FOLDER_MODAL:
            handleOpenWorkspaceModal(host);
            return;
        case AUTOMATION_ACTION_OPEN_PARAMETERS_MODAL:
            handleOpenParametersModal(host);
            return;
        case AUTOMATION_ACTION_ADD_TURN:
            handleAddTurn(host);
            return;
        case AUTOMATION_ACTION_REMOVE_TURN:
            handleRemoveTurn(host, element);
            return;
        case AUTOMATION_ACTION_SAVE_AUTOMATION:
            handleSaveAutomation(host);
            return;
        case AUTOMATION_ACTION_SAVE_CALENDAR_SETTINGS:
            handleSaveCalendarSettings(host);
            return;
        case AUTOMATION_ACTION_OPEN_CHAT_TRANSCRIPT: {
            handleOpenChatTranscript(host, element.dataset['conversationId'] ?? '');
            return;
        }
        case AUTOMATION_ACTION_RESET_PREFERENCES:
            handleResetPreferences(host);
            return;
        case AUTOMATION_ACTION_WINDOW_RUNS_ENTER_SELECT_MODE:
            host.windowRuns.enterWindowRunsSelectMode();
            return;
        case AUTOMATION_ACTION_WINDOW_RUNS_EXIT_SELECT_MODE:
            host.windowRuns.exitWindowRunsSelectMode();
            return;
        case AUTOMATION_ACTION_WINDOW_RUNS_TOGGLE_SELECTED:
            host.windowRuns.toggleWindowRunsOccurrenceSelected(requireZoneKey(element, 'Toggle window run selection'));
            return;
        case AUTOMATION_ACTION_WINDOW_RUNS_BATCH_DELETE:
            host.windowRuns.batchDeleteWindowRunsOccurrences();
            return;
        case AUTOMATION_ACTION_WINDOW_RUNS_DELETE_OCCURRENCE:
            host.windowRuns.deleteWindowRunsOccurrence(requireZoneKey(element, 'Delete window run occurrence'));
            return;
    }
};

export { dispatchAutomationPageAction };
export type { AutomationPageActionDispatcherHost } from '@pages/automation/controllers/actiondispatch/AutomationPageActionDispatcherHost.ts';
