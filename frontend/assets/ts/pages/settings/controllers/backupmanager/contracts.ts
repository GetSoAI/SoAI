/* SoAI - Settings page backup manager contracts [frontend/assets/ts/pages/settings/controllers/backupmanager/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SanitizerInput } from '@core/pagecontext/contracts.ts';
import type { AcceptedPowerActionResponse } from '@core/api/contracts/powerContracts.ts';
import type { DomEventHost, DomMutationHost, DomQueryHost, ExecutionHost, NotificationHost, SearchHost } from '@core/ui/controllerHosts.ts';
import type { BackupApiEntry, BackupEntry, BackupListLoadStatus, BackupOperationState } from '@core/settings/contracts.ts';
import type { OperationType } from '@features/overlays/public.ts';
import type { BackupTaskAcceptedResponse } from '@core/api/contracts/adminContracts.ts';
import type { StreamActionResult } from '@core/realtime/streammanager/types.ts';
import type { StreamActionHandlers } from '@core/types/streamTypes.ts';

interface BackupManagerDependencies {
    host: BackupManagerHost;
}

interface BackupManagerApiHost {
    isAdmin: () => boolean;
    listBackups: () => Promise<{ backups: BackupApiEntry[] }>;
    createBackup: () => Promise<BackupTaskAcceptedResponse>;
    restoreBackup: (backupId: string) => Promise<BackupTaskAcceptedResponse>;
    verifyBackup: (backupId: string) => Promise<BackupTaskAcceptedResponse>;
    deleteBackup: (backupId: string) => Promise<BackupTaskAcceptedResponse>;
    exportBackup: (backupId: string) => Promise<Response>;
    restartApplication: () => Promise<AcceptedPowerActionResponse>;
    showRestartOverlay: (value: OperationType) => void;
    sanitizeHtml: (value: SanitizerInput) => string;
    sanitizeAttribute: (value: SanitizerInput) => string;
}

interface BackupManagerDomHost extends DomQueryHost, DomEventHost, DomMutationHost {}

interface BackupManagerTaskHost {
    trackAcceptedTask: (taskId: string, options: { handlers: StreamActionHandlers; operation: { type: string } }) => StreamActionResult;
}

interface BackupManagerStateHost {
    getBackups: () => BackupEntry[];
    setBackups: (backups: BackupEntry[]) => void;
    getBackupListLoadStatus: () => BackupListLoadStatus;
    setBackupListLoadStatus: (status: BackupListLoadStatus) => void;
    getBackupOperation: () => BackupOperationState | null;
    setBackupOperation: (operation: BackupOperationState | null) => void;
}

interface BackupManagerHost {
    api: BackupManagerApiHost;
    dom: BackupManagerDomHost;
    tasks: BackupManagerTaskHost;
    state: BackupManagerStateHost;
    execution: ExecutionHost & { confirmAndExecute: NonNullable<ExecutionHost['confirmAndExecute']> };
    notifications: NotificationHost;
    search: SearchHost;
}

interface BackupProgressPayload {
    taskId: string;
    percent: number;
    message: string;
}

interface BackupCompletionPayload {
    taskId: string;
    success: boolean;
    message: string;
}

export { type BackupCompletionPayload, type BackupManagerApiHost, type BackupManagerDependencies, type BackupManagerDomHost, type BackupManagerHost, type BackupManagerStateHost, type BackupManagerTaskHost, type BackupProgressPayload };
