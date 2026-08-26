/* SoAI - Settings page backup manager constants [frontend/assets/ts/pages/settings/controllers/backupmanager/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const BACKUP_ACTION_CREATE = 'settings.backup.create';
const BACKUP_ACTION_RESTORE = 'settings.backup.restore';
const BACKUP_ACTION_VERIFY = 'settings.backup.verify';
const BACKUP_ACTION_DELETE = 'settings.backup.delete';
const BACKUP_ACTION_EXPORT = 'settings.backup.export';

type BackupActionId = typeof BACKUP_ACTION_CREATE | typeof BACKUP_ACTION_RESTORE | typeof BACKUP_ACTION_VERIFY | typeof BACKUP_ACTION_DELETE | typeof BACKUP_ACTION_EXPORT;

export { BACKUP_ACTION_CREATE, BACKUP_ACTION_RESTORE, BACKUP_ACTION_VERIFY, BACKUP_ACTION_DELETE, BACKUP_ACTION_EXPORT, type BackupActionId };
