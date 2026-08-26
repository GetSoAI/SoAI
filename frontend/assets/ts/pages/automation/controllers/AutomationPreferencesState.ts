/* SoAI - Automation preference corruption state ownership [frontend/assets/ts/pages/automation/controllers/AutomationPreferencesState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

class AutomationPreferencesState {
    #error: Error | null = null;

    get error(): Error | null {
        return this.#error;
    }

    get isCorrupt(): boolean {
        return this.#error !== null;
    }

    record(error: Error): void {
        this.#error = error;
    }

    clear(): void {
        this.#error = null;
    }
}

export { AutomationPreferencesState };
