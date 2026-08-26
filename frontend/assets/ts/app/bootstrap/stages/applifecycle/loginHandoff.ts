/* SoAI - Frontend application login handoff [frontend/assets/ts/app/bootstrap/stages/applifecycle/loginHandoff.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type LifecycleLoginOwner = WeakKey;

const activeLoginHandoffs: WeakMap<LifecycleLoginOwner, Promise<void>> = new WeakMap();

const runExclusiveLifecycleLogin = async (owner: LifecycleLoginOwner, taskFactory: () => Promise<void>): Promise<void> => {
    const activeTask = activeLoginHandoffs.get(owner);
    if (activeTask) {
        await activeTask;
        return;
    }
    const task = taskFactory().finally(() => {
        if (activeLoginHandoffs.get(owner) === task) {
            activeLoginHandoffs.delete(owner);
        }
    });
    activeLoginHandoffs.set(owner, task);
    await task;
};

export { runExclusiveLifecycleLogin };
