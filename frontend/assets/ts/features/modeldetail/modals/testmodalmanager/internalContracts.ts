/* SoAI - Model test modal internal contracts [frontend/assets/ts/features/modeldetail/modals/testmodalmanager/internalContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TestModalManagerHost, TestModalState } from '@features/modeldetail/modals/TestModalManagerTypes.ts';

export interface TestModalRuntimeContext {
    host: TestModalManagerHost;
    state: TestModalState;
    modalId: string;
    modalRoot: HTMLElement;
}

export interface RequestDetailElements {
    model: Element | null;
    mode: Element | null;
    started: Element | null;
    completed: Element | null;
    prompt: Element | null;
    responseContainer: Element | null;
    responseValue: Element | null;
}
