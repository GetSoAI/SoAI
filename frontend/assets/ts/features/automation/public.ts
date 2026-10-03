/* SoAI - Automation feature public surface [frontend/assets/ts/features/automation/public.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

export type { AutomationRealtimeUpdate, AutomationRunActivityServiceContract } from '@features/automation/runactivity/types.ts';
export { AutomationApiService } from '@features/automation/AutomationApiService.ts';
export type { AutomationApiClient } from '@features/automation/AutomationApiService.ts';
export type { AutomationColor, AutomationDataService, AutomationDefinitionResponse, AutomationDefinitionsPageResponse, AutomationLatestRunResponse, AutomationMcpCatalogResponse, AutomationModelOption, AutomationModelSettings, AutomationOccurrenceKeyRequest, AutomationOccurrenceResponse, AutomationOccurrencesDeleteResponse, AutomationOccurrencesPageResponse, AutomationRunResponse, AutomationSchedulePreviewRequest, AutomationSchedulePreviewResponse, AutomationWorkspaceAccess, CreateAutomationRequest, UpdateAutomationRequest } from '@features/automation/contracts.ts';
export { parseAutomationModelOptions } from '@features/automation/modelOptions.ts';
export { isAutomationActionId } from '@features/automation/actions.ts';
export type { AutomationActionId } from '@features/automation/actions.ts';
export {
    AUTOMATION_ACTION_ADD_TURN,
    AUTOMATION_ACTION_CONFLICT_KEEP_CHANGES,
    AUTOMATION_ACTION_CONFLICT_LOAD_LATEST,
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
    AUTOMATION_ACTION_OPEN_OCCURRENCE_DETAILS,
    AUTOMATION_ACTION_OPEN_PARAMETERS_MODAL,
    AUTOMATION_ACTION_REGISTRY_NEXT,
    AUTOMATION_ACTION_REGISTRY_PREVIOUS,
    AUTOMATION_ACTION_PREVIEW_AUTOMATION,
    AUTOMATION_ACTION_REMOVE_TURN,
    AUTOMATION_ACTION_RESET_PREFERENCES,
    AUTOMATION_ACTION_RETRY_EDITOR_PREREQUISITES,
    AUTOMATION_ACTION_RETRY_PAGE_DATA,
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
    AUTOMATION_ACTION_WINDOW_RUNS_TOGGLE_SELECTED
} from '@features/automation/actions.ts';
export { AUTOMATION_CALENDAR_SETTINGS_MODAL_ID, AUTOMATION_CONFIGURATION_MODAL_ID, AUTOMATION_OCCURRENCE_MODAL_ID, AUTOMATION_PARAMETERS_MODAL_ID } from '@features/automation/modals/constants.ts';
export { queryAutomationMcpModalDisableableControls, queryAutomationMcpServerToggleInputs, queryAutomationMcpToolToggleInputs, requireAutomationMcpToolsEmpty, requireAutomationMcpToolsList } from '@features/automation/modals/mcpDom.ts';
