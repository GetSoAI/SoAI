/* SoAI - Automation feature configuration modal markup [frontend/assets/ts/features/automation/modals/markup/configurationModalMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { buildWorkspaceFolderFieldMarkup } from '@core/fileexplorerbrowser/workspaceFolderFieldMarkup.ts';
import { buildMcpConversationSettingsBodyMarkup } from '@core/mcp/conversationSettingsMarkup.ts';
import { renderModalFooterActionButton, renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import { renderModalBody, renderModalLoadingState, renderModalScaffoldMarkup, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { toTrustedHtml, toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { uiAttr, uiHtml, uiText } from '@core/security/uiHtml.ts';
import { renderStandardDropdownSelectControl } from '@core/ui/dropdown/selectControl.ts';
import { renderFieldErrorMarkup } from '@core/ui/forms/fieldError.ts';
import { renderRequiredFieldLabel } from '@core/ui/forms/requiredMarker.ts';

import { AUTOMATION_ACTION_ADD_TURN, AUTOMATION_ACTION_CONFLICT_KEEP_CHANGES, AUTOMATION_ACTION_CONFLICT_LOAD_LATEST, AUTOMATION_ACTION_MODAL_EDIT, AUTOMATION_ACTION_OPEN_FOLDER_MODAL, AUTOMATION_ACTION_OPEN_PARAMETERS_MODAL, AUTOMATION_ACTION_RETRY_EDITOR_PREREQUISITES, AUTOMATION_ACTION_SAVE_AUTOMATION } from '@features/automation/actions.ts';
import { AUTOMATION_CONFIGURATION_MODAL_ID } from '@features/automation/modals/constants.ts';
import { renderAutomationColorPickerMarkup } from '@features/automation/modals/markup/colorPickerMarkup.ts';

const renderAutomationConfigurationModalMarkup = (): TrustedHtml => {
    const closeLabel = i18n.t('common.close');
    const createTitle = i18n.t('automation.modal.createTitle');
    const saveLabel = i18n.t('automation.modal.save');
    const cancelLabel = i18n.t('automation.modal.cancel');
    const editLabel = i18n.t('common.edit');
    const addLabel = i18n.t('automation.modal.addTurn');

    const recurrenceLabel = i18n.t('automation.modal.fields.recurrence');
    const startLabel = i18n.t('automation.modal.fields.start');
    const timezoneLabel = i18n.t('automation.modal.fields.timezone');
    const titleLabel = i18n.t('automation.modal.fields.title');
    const colorLabel = i18n.t('automation.modal.fields.color');
    const turnsLabel = i18n.t('automation.modal.fields.turns');
    const modelLabel = i18n.t('automation.modal.fields.model');
    const workspaceLabel = i18n.t('automation.modal.workspace.fieldLabel');
    const workspaceButton = i18n.t('automation.modal.workspace.button');
    const parametersLabel = i18n.t('automation.modal.parameters.fieldLabel');
    const parametersButton = i18n.t('automation.modal.parameters.button');
    const interactiveToolApprovalLabel = i18n.t('automation.modal.fields.interactiveToolApproval');
    const interactiveToolApprovalHint = i18n.t('automation.modal.fields.interactiveToolApprovalHint');
    const maxRunMinutesLabel = i18n.t('automation.modal.fields.maxRunMinutes');
    const maxRunMinutesHelp = i18n.t('automation.modal.fields.maxRunMinutesHelp');
    const recurrenceHelp = i18n.t('automation.modal.fields.recurrenceHelp');
    const modalId = AUTOMATION_CONFIGURATION_MODAL_ID;

    const retryLabel = i18n.t('common.retry');
    const keepChangesLabel = i18n.t('automation.modal.conflict.keepChanges');
    const loadLatestLabel = i18n.t('automation.modal.conflict.loadLatest');

    const header = renderStandardModalHeader({ modalId, title: createTitle, description: i18n.t('common.modalDescriptions.automationConfiguration'), closeLabel });
    const body = renderModalBody(
        uiHtml`
            <div id="${modalUiId(modalId, 'conflict')}" class="form-disclaimer automation-editor-notice u-hidden" role="alert">
                <p id="${modalUiId(modalId, 'conflict-message')}" class="automation-editor-notice-message"></p>
                <div class="automation-editor-notice-actions">
                    <button type="button" class="ui-button ui-variant-accent" data-action="${uiAttr(AUTOMATION_ACTION_CONFLICT_KEEP_CHANGES)}" aria-label="${uiAttr(keepChangesLabel)}" data-tooltip="${uiAttr(keepChangesLabel)}" data-modal-localize="text aria-label data-tooltip">${keepChangesLabel}</button>
                    <button type="button" class="ui-button ui-variant-neutral" data-action="${uiAttr(AUTOMATION_ACTION_CONFLICT_LOAD_LATEST)}" aria-label="${uiAttr(loadLatestLabel)}" data-tooltip="${uiAttr(loadLatestLabel)}" data-modal-localize="text aria-label data-tooltip">${loadLatestLabel}</button>
                </div>
            </div>
            <div id="${modalUiId(modalId, 'prerequisites-error')}" class="form-disclaimer form-disclaimer-error automation-editor-notice u-hidden" role="alert">
                <p id="${modalUiId(modalId, 'prerequisites-error-message')}" class="automation-editor-notice-message"></p>
                <div class="automation-editor-notice-actions">
                    <button type="button" id="${modalUiId(modalId, 'prerequisites-retry')}" class="ui-button ui-variant-neutral" data-action="${uiAttr(AUTOMATION_ACTION_RETRY_EDITOR_PREREQUISITES)}" aria-label="${uiAttr(retryLabel)}" data-tooltip="${uiAttr(retryLabel)}" data-modal-localize="text aria-label data-tooltip">${retryLabel}</button>
                </div>
            </div>
            <div id="${modalUiId(modalId, 'form')}" class="automation-editor-form">
            <div class="form-group setting-change-surface" data-automation-field="title">
                <label for="${modalUiId(modalId, 'title-input')}" data-modal-localize="text">${renderRequiredFieldLabel(titleLabel)}</label>
                <input id="${modalUiId(modalId, 'title-input')}" class="form-input" type="text" autocomplete="off" spellcheck="false" placeholder="${uiAttr(i18n.t('automation.modal.placeholders.title'))}" data-modal-localize="placeholder">
                ${renderFieldErrorMarkup(modalUiId(modalId, 'title-error'))}
            </div>
            <div class="form-group setting-change-surface" data-automation-field="color">
                <label id="${modalUiId(modalId, 'color-select-label')}" data-modal-localize="text">${colorLabel}</label>
                <div id="${modalUiId(modalId, 'color-select')}" class="automation-color-picker automation-color-select" role="radiogroup" aria-labelledby="${modalUiId(modalId, 'color-select-label')}">
                    ${toTrustedHtml(renderAutomationColorPickerMarkup(modalId))}
                </div>
            </div>
            <div class="form-group setting-change-surface" data-automation-field="timezone">
                <label for="${modalUiId(modalId, 'timezone-select')}" data-modal-localize="text">${renderRequiredFieldLabel(timezoneLabel)}</label>
                ${toTrustedUiHtml(renderStandardDropdownSelectControl(`<select id="${modalUiId(modalId, 'timezone-select')}" class="form-input"></select>`))}
                ${renderFieldErrorMarkup(modalUiId(modalId, 'timezone-error'))}
            </div>
            <div class="form-group setting-change-surface" data-automation-field="start">
                <label for="${modalUiId(modalId, 'start-input')}" data-modal-localize="text">${renderRequiredFieldLabel(startLabel)}</label>
                <input id="${modalUiId(modalId, 'start-input')}" class="form-input" type="datetime-local">
                ${renderFieldErrorMarkup(modalUiId(modalId, 'start-error'))}
            </div>
            <div class="form-group setting-change-surface" data-automation-field="recurrence">
                <label for="${modalUiId(modalId, 'recurrence-select')}" data-modal-localize="text">${renderRequiredFieldLabel(recurrenceLabel)}</label>
                ${toTrustedUiHtml(
                    renderStandardDropdownSelectControl(`<select id="${modalUiId(modalId, 'recurrence-select')}" class="form-input">
                    <option value="none" data-modal-localize="text">${uiText(i18n.t('automation.recurrence.none')).html}</option>
                    <option value="hourly" data-modal-localize="text">${uiText(i18n.t('automation.recurrence.hourly')).html}</option>
                    <option value="daily" data-modal-localize="text">${uiText(i18n.t('automation.recurrence.daily')).html}</option>
                    <option value="weekly" data-modal-localize="text">${uiText(i18n.t('automation.recurrence.weekly')).html}</option>
                    <option value="monthly" data-modal-localize="text">${uiText(i18n.t('automation.recurrence.monthly')).html}</option>
                    <option value="yearly" data-modal-localize="text">${uiText(i18n.t('automation.recurrence.yearly')).html}</option>
                </select>`)
                )}
                <div class="form-help" data-modal-localize="text">${recurrenceHelp}</div>
                ${renderFieldErrorMarkup(modalUiId(modalId, 'recurrence-error'))}
                <div id="${modalUiId(modalId, 'schedule-summary')}" class="form-help automation-schedule-summary" aria-live="polite"></div>
            </div>
            <div class="modal-body-section">
                <div class="form-group setting-change-surface" data-automation-field="model">
                    <label for="${modalUiId(modalId, 'model-input')}" data-modal-localize="text">${renderRequiredFieldLabel(modelLabel)}</label>
                    ${toTrustedUiHtml(renderStandardDropdownSelectControl(`<select id="${modalUiId(modalId, 'model-input')}" class="form-input model-selector automation-model-selector"></select>`))}
                    ${renderFieldErrorMarkup(modalUiId(modalId, 'model-error'))}
                </div>
                <div class="form-group setting-change-surface" data-automation-field="interactiveToolApproval">
                    <label for="${modalUiId(modalId, 'interactive-tool-approval-toggle')}" data-modal-localize="text">${interactiveToolApprovalLabel}</label>
                    <div class="toggle-switch">
                        <input id="${modalUiId(modalId, 'interactive-tool-approval-toggle')}" type="checkbox">
                        <label class="slider" for="${modalUiId(modalId, 'interactive-tool-approval-toggle')}"></label>
                    </div>
                    <div class="form-help" data-modal-localize="text">${interactiveToolApprovalHint}</div>
                </div>
                ${buildWorkspaceFolderFieldMarkup({
                    pathInputId: modalUiId(modalId, 'workspace-path-input'),
                    changeButtonId: modalUiId(modalId, 'workspace-change-button'),
                    label: workspaceLabel,
                    buttonLabel: workspaceButton,
                    action: AUTOMATION_ACTION_OPEN_FOLDER_MODAL,
                    status: false,
                    fieldClassName: 'automation-modal-settings-field',
                    rowClassName: 'automation-modal-settings-row',
                    mainClassName: 'automation-modal-settings-main',
                    actionClassName: 'automation-modal-settings-action',
                    fieldAttributes: uiHtml` data-automation-field="workspace"`
                })}
                <div class="form-group setting-change-surface chat-config-span-2 automation-modal-settings-field" data-automation-field="parameters">
                    <label for="${modalUiId(modalId, 'parameters-summary-input')}" data-modal-localize="text">${parametersLabel}</label>
                    <div class="form-row-split form-row-split--with-action automation-modal-settings-row">
                        <div class="form-col-main automation-modal-settings-main">
                            <input id="${modalUiId(modalId, 'parameters-summary-input')}" class="form-input" type="text" readonly>
                        </div>
                        <div class="form-col-action automation-modal-settings-action">
                            <button type="button" id="${modalUiId(modalId, 'parameters-button')}" class="ui-button" data-action="${uiAttr(AUTOMATION_ACTION_OPEN_PARAMETERS_MODAL)}" aria-label="${uiAttr(parametersButton)}" data-tooltip="${uiAttr(parametersButton)}" data-modal-localize="text aria-label data-tooltip">${parametersButton}</button>
                        </div>
                    </div>
                </div>
            </div>
            <div class="modal-body-section">
                <div class="form-group setting-change-surface" data-automation-field="maxRunMinutes">
                    <label for="${modalUiId(modalId, 'max-run-minutes-input')}" data-modal-localize="text">${renderRequiredFieldLabel(maxRunMinutesLabel)}</label>
                    <input id="${modalUiId(modalId, 'max-run-minutes-input')}" class="form-input" type="number" min="1" max="1440">
                    <div class="form-help" data-modal-localize="text">${maxRunMinutesHelp}</div>
                    ${renderFieldErrorMarkup(modalUiId(modalId, 'max-run-minutes-error'))}
                </div>
            </div>
            <div class="modal-body-section">
                <div class="form-group setting-change-surface" data-automation-field="turns">
                    <label data-modal-localize="text">${renderRequiredFieldLabel(turnsLabel)} <span id="${modalUiId(modalId, 'turns-char-counter')}" class="automation-turn-char-counter" data-modal-localize="text">${i18n.t('automation.modal.counters.turnChars', { used: 0 })}</span></label>
                    <div id="${modalUiId(modalId, 'turns-container')}" class="automation-turns-container">
                        <div id="${modalUiId(modalId, 'turns-list')}" class="automation-turns-list" role="list" aria-label="${uiAttr(turnsLabel)}" data-modal-localize="aria-label"></div>
                        ${renderFieldErrorMarkup(modalUiId(modalId, 'turns-error'))}
                        <button type="button" class="ui-button ui-variant-accent automation-add-turn-button" id="${modalUiId(modalId, 'add-turn-button')}" data-action="${uiAttr(AUTOMATION_ACTION_ADD_TURN)}" aria-label="${uiAttr(addLabel)}" data-tooltip="${uiAttr(addLabel)}" data-modal-localize="text aria-label data-tooltip">${addLabel}</button>
                    </div>
                </div>
            </div>
            <div class="modal-body-section setting-change-surface" data-automation-field="mcp">
                <div id="${modalUiId(modalId, 'tools-unavailable')}" class="form-disclaimer automation-editor-notice u-hidden" role="status">
                    <p class="automation-editor-notice-message" data-modal-localize="text">${uiText(i18n.t('automation.modal.prerequisites.toolsUnavailable'))}</p>
                    <div class="automation-editor-notice-actions">
                        <button type="button" class="ui-button ui-variant-neutral" data-action="${uiAttr(AUTOMATION_ACTION_RETRY_EDITOR_PREREQUISITES)}" aria-label="${uiAttr(retryLabel)}" data-tooltip="${uiAttr(retryLabel)}" data-modal-localize="text aria-label data-tooltip">${retryLabel}</button>
                    </div>
                </div>
                ${toTrustedHtml(
                    buildMcpConversationSettingsBodyMarkup({
                        modalId,
                        disableInteractions: true,
                        includeServersList: false,
                        strings: {
                            serversEmpty: uiText(i18n.t('chat.configuration.mcp.noServers')).html,
                            toolsEmpty: uiText(i18n.t('chat.configuration.mcp.noTools')).html,
                            enabledLabelAttr: uiAttr(i18n.t('common.enabled')).html,
                            disabledLabelAttr: uiAttr(i18n.t('common.disabled')).html,
                            disabledLabel: uiText(i18n.t('common.disabled')).html
                        }
                    })
                )}
            </div>
            ${renderFieldErrorMarkup(modalUiId(modalId, 'mcp-error'))}
            <div id="${modalUiId(modalId, 'modal-error')}" class="form-disclaimer form-disclaimer-error u-hidden" role="alert"></div>
            </div>
            ${renderModalLoadingState({ id: modalUiId(modalId, 'prerequisites-loading'), text: i18n.t('common.loading'), hidden: true })}
        `,
        {}
    );
    const footer = renderSplitModalFooter({
        left: renderModalFooterCloseButton({ modalId, id: modalUiId(modalId, 'close-button'), text: cancelLabel }),
        right: uiHtml`${renderModalFooterActionButton({
            text: editLabel,
            id: modalUiId(modalId, 'edit-button'),
            variant: 'warning',
            action: AUTOMATION_ACTION_MODAL_EDIT,
            className: 'u-hidden'
        })}${renderModalFooterActionButton({
            text: saveLabel,
            id: modalUiId(modalId, 'save-button'),
            variant: 'accent',
            action: AUTOMATION_ACTION_SAVE_AUTOMATION
        })}`
    });
    return renderModalScaffoldMarkup({ id: modalId, header, body, footer, rootAttributes: { 'data-page-scope': 'automation' } });
};

export { renderAutomationConfigurationModalMarkup };
