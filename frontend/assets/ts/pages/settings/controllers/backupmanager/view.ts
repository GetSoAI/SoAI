/* SoAI - Settings page backup manager rendering [frontend/assets/ts/pages/settings/controllers/backupmanager/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { SanitizerInput } from '@core/pagecontext/contracts.ts';
import { formatNullableEpochMsWithFallback } from '@core/primitives/dateTime.ts';
import { formatBytes } from '@core/primitives/byteSize.ts';
import type { BackupEntry, BackupListLoadStatus } from '@core/settings/contracts.ts';
import { renderAdminOnlyNotice } from '@core/settings/adminOnlyNotice.ts';
import { renderSection, renderSettingsRecordList, renderSettingsSubgroup } from '@core/settings/settingsMarkup.ts';
import { renderSettingsTitlebarAddButton } from '@core/settings/titlebarActions.ts';
import { renderControlDisabledAttributes } from '@core/ui/controls/disabledState.ts';
import { renderEmptyState } from '@core/ui/emptyState.ts';
import { UI_IDS } from '@features/settings/public.ts';
import { BACKUP_ACTION_CREATE, BACKUP_ACTION_DELETE, BACKUP_ACTION_EXPORT, BACKUP_ACTION_RESTORE, BACKUP_ACTION_VERIFY } from '@pages/settings/controllers/backupmanager/constants.ts';

interface BackupRenderContext {
    isAdmin: boolean;
    backups: BackupEntry[];
    listLoadStatus: BackupListLoadStatus;
    isOperating: boolean;
    sanitizeHtml: (value: SanitizerInput) => string;
    sanitizeAttribute: (value: SanitizerInput) => string;
}

interface BackupItemActionContext {
    backupId: string;
    actionsDisabled: boolean;
    operationDisabled: boolean;
    sanitizeAttribute: (value: SanitizerInput) => string;
}

const renderBackupSection = ({ isAdmin, backups, listLoadStatus, isOperating, sanitizeHtml, sanitizeAttribute }: BackupRenderContext): string => {
    if (!isAdmin) {
        return renderSection({
            title: i18n.t('settings.backup.sectionTitle'),
            description: i18n.t('settings.backup.sectionDescription'),
            className: 'settings-section--backup',
            content: renderAdminOnlyNotice(i18n.t('settings.adminOnlyRequired')).html
        });
    }

    const createButtonLabel = i18n.t('settings.backup.actions.create');
    const createBtn = renderSettingsTitlebarAddButton({ id: UI_IDS.BACKUP_CREATE, action: BACKUP_ACTION_CREATE, label: createButtonLabel, disabled: isOperating });

    return renderSection({
        title: i18n.t('settings.backup.sectionTitle'),
        description: i18n.t('settings.backup.sectionDescription'),
        className: 'settings-section--backup',
        trailing: createBtn,
        content: `<div id="${UI_IDS.BACKUP_PROGRESS}" class="settings-operation-progress-slot"></div>${renderSettingsSubgroup({
            title: i18n.t('settings.backup.list.title'),
            description: i18n.t('settings.backup.list.description'),
            content: renderBackupListContainer(backups, sanitizeHtml, sanitizeAttribute, isOperating, listLoadStatus)
        })}`
    });
};

const renderBackupListContainer = (backups: BackupEntry[], sanitizeHtml: (value: SanitizerInput) => string, sanitizeAttribute: (value: SanitizerInput) => string, isOperating: boolean, listLoadStatus: BackupListLoadStatus): string => {
    return renderSettingsRecordList({
        id: UI_IDS.BACKUP_LIST,
        items: renderBackupList(backups, sanitizeHtml, sanitizeAttribute, isOperating),
        empty: renderBackupListState(listLoadStatus)
    });
};

const renderBackupListContent = (backups: BackupEntry[], sanitizeHtml: (value: SanitizerInput) => string, sanitizeAttribute: (value: SanitizerInput) => string, isOperating: boolean, listLoadStatus: BackupListLoadStatus): string => {
    const items = renderBackupList(backups, sanitizeHtml, sanitizeAttribute, isOperating);
    return items.length ? items.join('') : renderBackupListState(listLoadStatus);
};

const renderBackupListState = (listLoadStatus: BackupListLoadStatus): string => {
    if (listLoadStatus === 'loaded') {
        return renderEmptyState({ title: i18n.t('settings.backup.list.empty'), className: 'ui-empty-state--simple' }).html;
    }
    if (listLoadStatus === 'failed') {
        return renderEmptyState({ title: i18n.t('settings.backup.errors.reloadFailed'), className: 'ui-empty-state--simple' }).html;
    }
    return renderEmptyState({ title: i18n.t('common.loading'), className: 'ui-empty-state--simple' }).html;
};

const renderBackupList = (backups: BackupEntry[], sanitizeHtml: (value: SanitizerInput) => string, sanitizeAttribute: (value: SanitizerInput) => string, isOperating: boolean): string[] =>
    backups.map((backup) => {
        const createdDate = formatNullableEpochMsWithFallback(backup.createdAt, i18n.t('common.notAvailable'));
        const sizeDisplay = backup.sizeBytes !== null ? formatBytes(backup.sizeBytes) : i18n.t('common.notAvailable');
        const statusClass = backup.valid ? 'settings-record-badge--active' : 'settings-record-badge--danger';
        const statusLabel = backup.valid ? i18n.t('settings.backup.list.valid') : i18n.t('settings.backup.list.invalid');
        const actionsDisabled = isOperating || !backup.valid;
        const operationDisabled = isOperating;
        const backupId = sanitizeAttribute(backup.backupId);
        const validValue = backup.valid ? 'true' : 'false';

        return `<div class="settings-record-item" data-backup-id="${backupId}" data-backup-valid="${validValue}">${renderBackupItemInfo(backup, sanitizeHtml, statusClass, statusLabel, createdDate, sizeDisplay)}${renderBackupItemActions({
            backupId,
            actionsDisabled,
            operationDisabled,
            sanitizeAttribute
        })}</div>`;
    });

const renderBackupItemInfo = (backup: BackupEntry, sanitizeHtml: (value: SanitizerInput) => string, statusClass: string, statusLabel: string, createdDate: string, sizeDisplay: string): string => {
    const recoveryWarning = backup.licensingRecoveryState === 'incomplete' ? `<span class="settings-record-warning">${sanitizeHtml(i18n.t('settings.backup.list.licensingIncomplete'))}</span>` : '';
    return `<div class="settings-record-info backup-info"><div class="settings-record-header backup-header"><span class="settings-record-label backup-id">${sanitizeHtml(backup.backupId)}</span><span class="settings-record-badge ${statusClass}">${statusLabel}</span></div><div class="settings-record-meta backup-meta"><span>${i18n.t('settings.backup.list.created_at')}: ${sanitizeHtml(createdDate)}</span><span>${i18n.t('settings.backup.list.size')}: ${sanitizeHtml(sizeDisplay)}</span>${recoveryWarning}</div></div>`;
};

const renderBackupItemActions = (context: BackupItemActionContext): string => {
    const verifyLabel = i18n.t('settings.backup.actions.verify');
    const exportLabel = i18n.t('settings.backup.actions.download');
    const restoreLabel = i18n.t('settings.backup.actions.restore');
    const deleteLabel = i18n.t('settings.backup.actions.delete');
    const { backupId, actionsDisabled, operationDisabled, sanitizeAttribute } = context;
    const verifyLabelAttr = sanitizeAttribute(verifyLabel);
    const exportLabelAttr = sanitizeAttribute(exportLabel);
    const restoreLabelAttr = sanitizeAttribute(restoreLabel);
    const deleteLabelAttr = sanitizeAttribute(deleteLabel);

    return `<div class="settings-record-actions backup-actions"><button type="button" class="ui-button ui-button--sm ui-variant-neutral backup-verify-btn" data-action="${BACKUP_ACTION_VERIFY}" data-backup-id="${backupId}" aria-label="${verifyLabelAttr}" data-tooltip="${verifyLabelAttr}"${renderControlDisabledAttributes(actionsDisabled)}>${verifyLabel}</button><button type="button" class="ui-button ui-button--sm ui-variant-success backup-export-btn" data-action="${BACKUP_ACTION_EXPORT}" data-backup-id="${backupId}" aria-label="${exportLabelAttr}" data-tooltip="${exportLabelAttr}"${renderControlDisabledAttributes(operationDisabled)}>${exportLabel}</button><button type="button" class="ui-button ui-button--sm ui-variant-warning backup-restore-btn" data-action="${BACKUP_ACTION_RESTORE}" data-backup-id="${backupId}" aria-label="${restoreLabelAttr}" data-tooltip="${restoreLabelAttr}"${renderControlDisabledAttributes(actionsDisabled)}>${restoreLabel}</button><button type="button" class="ui-button ui-button--sm ui-variant-danger backup-delete-btn" data-action="${BACKUP_ACTION_DELETE}" data-backup-id="${backupId}" aria-label="${deleteLabelAttr}" data-tooltip="${deleteLabelAttr}"${renderControlDisabledAttributes(operationDisabled)}>${deleteLabel}</button></div>`;
};

export { renderBackupListContent, renderBackupSection };
