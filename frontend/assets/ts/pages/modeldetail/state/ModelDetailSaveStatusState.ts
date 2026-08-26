/* SoAI - Model detail save-busy state ownership [frontend/assets/ts/pages/modeldetail/state/ModelDetailSaveStatusState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

class ModelDetailSaveStatusState {
    #busy = false;

    get busy(): boolean {
        return this.#busy;
    }

    update(busy: boolean): void {
        this.#busy = busy;
    }

    reset(): void {
        this.#busy = false;
    }
}

export { ModelDetailSaveStatusState };
