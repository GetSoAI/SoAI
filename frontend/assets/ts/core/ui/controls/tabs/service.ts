/* SoAI - Shared UI tabs service [frontend/assets/ts/core/ui/controls/tabs/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray, isObject } from '@core/typeGuards.ts';
import type { GeometryBox } from '@core/layout/elementGeometry.ts';
import type { RightButtonConfig, TabConfig, TabsOptions } from '@core/ui/controls/tabs/types.ts';

interface NormalizedTabsOptions {
    tabs: TabConfig[];
    rightButtons: Record<string, RightButtonConfig[]>;
    onTabChange: ((activeTab: string, previousTab: string | null) => void) | null;
    activeTab: string | null;
    enableOverflowNav: boolean;
    navScrollAmount: number;
}

const normalizeTabsOptions = (options: TabsOptions): NormalizedTabsOptions => {
    const tabs = isArray(options.tabs) ? options.tabs : [];
    const rightButtons = isObject(options.rightButtons) ? options.rightButtons : {};
    const activeTab = options.activeTab ?? tabs[0]?.id ?? null;
    const configuredScrollAmount = options.navScrollAmount;
    return {
        tabs,
        rightButtons,
        onTabChange: typeof options.onTabChange === 'function' ? options.onTabChange : null,
        activeTab,
        enableOverflowNav: options.enableOverflowNav !== false,
        navScrollAmount: typeof configuredScrollAmount === 'number' && Number.isFinite(configuredScrollAmount) ? configuredScrollAmount : 0.8
    };
};

const findRightButtonConfig = (buttonId: string, activeTab: string | null, rightButtons: Record<string, RightButtonConfig[]>): RightButtonConfig | null => {
    const currentButtons = activeTab ? rightButtons[activeTab] : undefined;
    if (isArray(currentButtons)) {
        const currentMatch = currentButtons.find((button) => button.id === buttonId);
        if (currentMatch) {
            return currentMatch;
        }
    }
    for (const buttons of Object.values(rightButtons)) {
        if (!isArray(buttons)) {
            continue;
        }
        const persistent = buttons.find((button) => button.id === buttonId && button.persistent);
        if (persistent) {
            return persistent;
        }
    }
    return null;
};

const findFirstEnabledTab = (tabs: TabConfig[], getElementByTabId: (tabId: string) => Element | null | undefined): TabConfig | null => {
    for (const tab of tabs) {
        const element = getElementByTabId(tab.id);
        if (element instanceof HTMLButtonElement && !element.disabled) {
            return tab;
        }
    }
    return null;
};

const resolveNotifyBadgeText = (count: number): string => (count > 99 ? '99+' : String(count));

const calculateTabScrollOffset = (navRect: GeometryBox, tabRect: GeometryBox): number => {
    if (tabRect.left < navRect.left) {
        return tabRect.left - navRect.left - 16;
    }
    if (tabRect.right > navRect.right) {
        return tabRect.right - navRect.right + 16;
    }
    return 0;
};

export { calculateTabScrollOffset, findFirstEnabledTab, findRightButtonConfig, normalizeTabsOptions, resolveNotifyBadgeText };
