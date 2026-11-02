/* SoAI - Settings page confirmed action execution service [frontend/assets/ts/pages/settings/controllers/page/confirmedactionexecution/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { ConfirmationOptions } from '@core/ui/modals/dialogs/types.ts';

interface SettingsConfirmedActionHost {
    withButtonDisabled: <T>(button: Element, functionValue: () => Promise<T>, options?: { keepDisabled?: boolean }) => Promise<T>;
    confirmAndExecute: <Result>(boundaryName: string, confirmOptions: Omit<ConfirmationOptions, 'owner'> | null, action: () => Promise<Result>, successMessage: string | null, onSuccess: (() => Promise<void> | void) | null, onError: ((error: Error) => void) | null) => Promise<void>;
}

interface ConfirmedButtonActionOptions<Result> {
    host: SettingsConfirmedActionHost;
    button: HTMLButtonElement;
    boundaryName: string;
    confirmOptions: Omit<ConfirmationOptions, 'owner'> | null;
    action: () => Promise<Result>;
    successMessage?: string | null;
    afterSuccess?: (() => Promise<void> | void) | null;
    onError?: ((error: Error) => void) | null;
    onActionError?: ((error: Error) => void) | null;
    keepDisabled?: boolean | undefined;
}

const executeConfirmedButtonAction = async <Result>(options: ConfirmedButtonActionOptions<Result>): Promise<void> => {
    const buttonOptions = options.keepDisabled === true ? { keepDisabled: true } : undefined;
    await options.host.confirmAndExecute(
        options.boundaryName,
        options.confirmOptions,
        async (): Promise<Result> => {
            try {
                return await options.host.withButtonDisabled(options.button, options.action, buttonOptions);
            } catch (error) {
                const runtimeError = ensureError(error);
                if (!isAbortError(runtimeError)) options.onActionError?.(runtimeError);
                throw runtimeError;
            }
        },
        options.successMessage ?? null,
        options.afterSuccess ?? null,
        options.onError ?? null
    );
};

export { executeConfirmedButtonAction };
export type { SettingsConfirmedActionHost };
