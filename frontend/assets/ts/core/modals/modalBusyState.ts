/* SoAI - Shared modal busy-state orchestration [frontend/assets/ts/core/modals/modalBusyState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { setAriaBusy } from '@core/ui/controls/ariaBusy.ts';
import { createBusyDisabledToken, setBusyDisabledState, type BusyDisabledTarget, type BusyDisabledToken } from '@core/ui/controls/busyDisabledState.ts';
import { beginLoadingButton, endLoadingButton } from '@core/ui/loadingbuttons/service.ts';

interface ModalBusyControl {
    element: BusyDisabledTarget;
    spinner?: 'overlay' | 'none' | undefined;
}

interface ModalBusyState {
    setBusy: (busy: boolean) => void;
}

interface ModalBusyStateOptions {
    loadingButton?: BusyDisabledTarget | null | undefined;
    controls?: readonly ModalBusyControl[] | undefined;
}

const createModalBusyState = (modal: HTMLElement, options: ModalBusyStateOptions = {}): ModalBusyState => {
    let loadingButtonToken: BusyDisabledToken | null = null;
    const controlTokens = new Map<BusyDisabledTarget, BusyDisabledToken>();

    const setBusy = (busy: boolean): void => {
        setAriaBusy(modal, busy);
        const loadingButton = options.loadingButton ?? null;
        if (loadingButton !== null) {
            if (busy) {
                if (loadingButtonToken === null) {
                    loadingButtonToken = beginLoadingButton(loadingButton);
                }
            } else if (loadingButtonToken !== null) {
                endLoadingButton(loadingButton, loadingButtonToken);
                loadingButtonToken = null;
            }
        }

        const controls = options.controls ?? [];
        for (const control of controls) {
            if (busy) {
                if (!controlTokens.has(control.element)) {
                    const token = setBusyDisabledState(control.element, {
                        isBusy: true,
                        createToken: createBusyDisabledToken,
                        spinner: control.spinner ?? 'none'
                    });
                    controlTokens.set(control.element, token);
                }
                continue;
            }
            const token = controlTokens.get(control.element) ?? null;
            if (token === null) {
                continue;
            }
            setBusyDisabledState(control.element, { isBusy: false, token });
            controlTokens.delete(control.element);
        }
    };

    return { setBusy };
};

const runModalBusyAction = async <TResult>(busyState: ModalBusyState, action: () => Promise<TResult>): Promise<TResult> => {
    try {
        busyState.setBusy(true);
        return await action();
    } finally {
        busyState.setBusy(false);
    }
};

export { createModalBusyState, runModalBusyAction };
export type { ModalBusyControl, ModalBusyState, ModalBusyStateOptions };
