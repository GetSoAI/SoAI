/* SoAI - Settings page backup manager validation [frontend/assets/ts/pages/settings/controllers/backupmanager/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';
import { BACKUP_ACTION_CREATE, BACKUP_ACTION_DELETE, BACKUP_ACTION_EXPORT, BACKUP_ACTION_RESTORE, BACKUP_ACTION_VERIFY, type BackupActionId } from '@pages/settings/controllers/backupmanager/constants.ts';

const { guard: isBackupActionId } = createActionIdSet<BackupActionId>(BACKUP_ACTION_CREATE, BACKUP_ACTION_RESTORE, BACKUP_ACTION_VERIFY, BACKUP_ACTION_DELETE, BACKUP_ACTION_EXPORT);

export { isBackupActionId };
