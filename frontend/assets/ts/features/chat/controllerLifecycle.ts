/* SoAI - Chat feature controller lifecycle [frontend/assets/ts/features/chat/controllerLifecycle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type DisposableController = Readonly<{
    dispose(): void;
}>;

const disposeChatController = <T extends DisposableController>(controller: T | null): null => {
    controller?.dispose();
    return null;
};

const runDisposerCallbacks = (disposers: Array<() => void>): void => {
    for (const dispose of disposers) {
        dispose();
    }
};

export { disposeChatController, runDisposerCallbacks };
export type { DisposableController };
