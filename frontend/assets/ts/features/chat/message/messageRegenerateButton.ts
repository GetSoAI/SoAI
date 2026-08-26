/* SoAI - Chat feature message regenerate button [frontend/assets/ts/features/chat/message/messageRegenerateButton.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { beginLoadingButton, endLoadingButton } from '@core/ui/loadingbuttons/service.ts';

type RegenerateButtonLoadingToken = string;

function setRegenerateButtonLoading(button: HTMLButtonElement, isLoading: true): RegenerateButtonLoadingToken;
function setRegenerateButtonLoading(button: HTMLButtonElement, isLoading: false, token: RegenerateButtonLoadingToken): void;
function setRegenerateButtonLoading(button: HTMLButtonElement, isLoading: boolean, token?: RegenerateButtonLoadingToken): RegenerateButtonLoadingToken | void {
    if (isLoading) {
        return beginLoadingButton(button);
    }

    if (typeof token !== 'string' || token.length === 0) {
        throw new Error('setRegenerateButtonLoading requires a token to clear loading');
    }
    return endLoadingButton(button, token);
}

export { setRegenerateButtonLoading };
export type { RegenerateButtonLoadingToken };
