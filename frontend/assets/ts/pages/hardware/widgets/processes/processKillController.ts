/* SoAI - Hardware page process kill controller [frontend/assets/ts/pages/hardware/widgets/processes/processKillController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { beginLoadingButton, clearLoadingButtonIfNeeded } from '@core/ui/loadingbuttons/service.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { normalizeKillOptions, resolveKillProcessError } from '@pages/hardware/widgets/processes/effects.ts';
import { normalizeProcessRecord, resolveProcessDisplayName } from '@pages/hardware/widgets/processes/mappers.ts';
import type { ProcessRecord, ProcessTableManagerDependencies } from '@pages/hardware/widgets/processes/types.ts';

type ProcessKillControllerHost = {
    canKillProcesses: () => boolean;
    getProcessList: () => readonly ProcessRecord[];
};

class ProcessKillController {
    readonly #dependencies: ProcessTableManagerDependencies;
    readonly #host: ProcessKillControllerHost;
    readonly #pendingKills: Set<string> = new Set();
    #supportsElevatedKillCache: boolean | null = null;

    constructor(dependencies: ProcessTableManagerDependencies, host: ProcessKillControllerHost) {
        this.#dependencies = dependencies;
        this.#host = host;
    }

    handleKillAction(target: Element): Promise<void> {
        return this.#dependencies.runWithBoundary('hardware:killProcess', async () => {
            if (!this.#host.canKillProcesses()) {
                return;
            }
            const pidAttr = (target.getAttribute('data-pid') ?? '').trim();
            const pidValue = Number(pidAttr);
            if (!pidAttr || Number.isNaN(pidValue) || pidValue <= 0 || this.#pendingKills.has(pidAttr)) {
                return;
            }
            const name = this.getProcessDisplayName(pidValue);
            const confirmed = await requireDialogsService().showConfirmation({
                title: i18n.t('hardware.processes.confirmKill.title'),
                message: i18n.t('hardware.processes.confirmKill.message', { name, pid: pidValue }),
                confirmText: i18n.t('hardware.processes.confirmKill.confirmButton'),
                cancelText: i18n.t('hardware.processes.confirmKill.cancelButton'),
                variant: 'danger'
            });
            if (!confirmed) {
                return;
            }
            const button = target instanceof HTMLButtonElement ? target : null;
            await this.executeProcessKill(button, pidAttr, name);
        });
    }

    handleSnapshotUpdate(): void {
        this.#supportsElevatedKillCache = null;
    }

    getProcessDisplayName(pid: number | string): string {
        const targetPid = Number(pid);
        const process = this.#host.getProcessList().find((entry) => Number(entry?.pid) === targetPid);
        return process ? resolveProcessDisplayName(normalizeProcessRecord(process)) : i18n.t('hardware.processes.unknownProcess');
    }

    dispose(): void {
        this.#supportsElevatedKillCache = null;
        this.#pendingKills.clear();
    }

    async executeProcessKill(button: HTMLButtonElement | null, pid: string, processName: string, options: { signal?: number; useSudo?: boolean } = {}): Promise<void> {
        const normalizedPid = pid.trim();
        if (!normalizedPid || this.#pendingKills.has(normalizedPid)) return;
        this.#pendingKills.add(normalizedPid);
        this.#setProcessKillButtonState(button, true);
        const normalizedOptions = normalizeKillOptions(options);
        const pidNumber = Number(normalizedPid);
        const displayPid = Number.isFinite(pidNumber) && pidNumber > 0 ? pidNumber : normalizedPid;
        try {
            await this.#dependencies.runWithBoundary('hardware:killProcess', async () => {
                let response: Awaited<ReturnType<ProcessTableManagerDependencies['killProcess']>> = null;
                let killError: Error | null = null;
                try {
                    response = await this.#dependencies.killProcess(normalizedPid, {
                        signal: normalizedOptions.signal,
                        useSudo: normalizedOptions.useSudo,
                        throwOnError: false,
                        notifyOnError: false
                    });
                } catch (error) {
                    killError = ensureError(error);
                }
                if (response) {
                    this.#dependencies.showNotification(
                        i18n.t('hardware.processes.notifications.killSuccess', {
                            name: processName,
                            pid: displayPid
                        }),
                        'success'
                    );
                    return;
                }
                const resolution = resolveKillProcessError({
                    error: killError ?? new Error('Kill process failed'),
                    pid: displayPid,
                    processName,
                    attemptedSudo: normalizedOptions.useSudo,
                    supportsElevatedKill: this.#supportsElevatedKill()
                });
                if (resolution.retryElevated) {
                    this.#pendingKills.delete(normalizedPid);
                    this.#setProcessKillButtonState(button, false);
                    const confirmed = await requireDialogsService().showConfirmation({
                        title: i18n.t('hardware.processes.confirmKillElevated.title'),
                        message: i18n.t('hardware.processes.confirmKillElevated.message', { name: processName, pid: displayPid }),
                        confirmText: i18n.t('hardware.processes.confirmKillElevated.confirmButton'),
                        cancelText: i18n.t('hardware.processes.confirmKillElevated.cancelButton'),
                        variant: 'warning'
                    });
                    if (confirmed) {
                        await this.executeProcessKill(button, normalizedPid, processName, {
                            signal: normalizedOptions.signal,
                            useSudo: true
                        });
                    }
                    return;
                }
                this.#dependencies.showNotification(resolution.message, resolution.type);
            });
        } finally {
            this.#pendingKills.delete(normalizedPid);
            this.#setProcessKillButtonState(button, false);
        }
    }

    #supportsElevatedKill(): boolean {
        if (this.#supportsElevatedKillCache !== null) return this.#supportsElevatedKillCache;
        const snapshot = this.#dependencies.getLastSnapshot();
        const platform = typeof snapshot?.capabilities?.platform === 'string' ? snapshot.capabilities.platform : '';
        this.#supportsElevatedKillCache = !platform.toLowerCase().includes('win');
        return this.#supportsElevatedKillCache;
    }

    #setProcessKillButtonState(button: HTMLButtonElement | null, isLoading: boolean): void {
        if (!button) return;
        if (isLoading) {
            beginLoadingButton(button);
            return;
        }
        clearLoadingButtonIfNeeded(button);
    }
}

export { ProcessKillController };
