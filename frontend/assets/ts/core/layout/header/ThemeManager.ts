/* SoAI - Shared layout theme manager [frontend/assets/ts/core/layout/header/ThemeManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getLayoutRuntimeManager } from '@core/runtime/LayoutManager.ts';

interface ThemeStorage {
    getTheme: () => string | null;
    setTheme: (theme: string) => void;
}

export interface ThemeManagerHost {
    getStorage: () => ThemeStorage;
    updateLogosForTheme: () => void;
}

interface ThemeManagerOptions {
    header: ThemeManagerHost;
}

export class ThemeManager {
    private header: ThemeManagerHost;
    private currentTheme: string;

    constructor({ header }: ThemeManagerOptions) {
        this.header = header;
        this.currentTheme = 'dark';
    }

    async initialize(): Promise<void> {
        const storage = this.header.getStorage();
        const storedTheme = storage.getTheme();
        if (storedTheme) {
            this.currentTheme = storedTheme;
        }
        storage.setTheme(this.currentTheme);
        this.applyTheme();
    }

    destroy(): void {}

    handleThemeEvent = (theme: string | undefined): void => {
        const normalized = typeof theme === 'string' ? theme : '';
        if (normalized && normalized !== this.currentTheme) {
            this.set(normalized);
        }
    };

    set(theme: string): void {
        if (!theme || theme === this.currentTheme) {
            return;
        }
        this.currentTheme = theme;
        const storage = this.header.getStorage();
        storage.setTheme(this.currentTheme);
        this.applyTheme();
    }

    applyTheme(): void {
        if (this.currentTheme) {
            getLayoutRuntimeManager().setBodyAttribute('data-theme', this.currentTheme);
        } else {
            getLayoutRuntimeManager().removeBodyAttribute('data-theme');
        }
        this.header.updateLogosForTheme();
    }
}
