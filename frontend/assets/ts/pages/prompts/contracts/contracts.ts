/* SoAI - Prompts page boundary contracts [frontend/assets/ts/pages/prompts/contracts/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PromptRecord } from '@features/prompts/public.ts';
import { DEFAULT_GROUP_KEY } from '@pages/prompts/contracts/constants.ts';

export interface PromptColorGroup {
    key: string;
    value: string | null;
}

export interface ColorToolkitInterface {
    applyToModal(modalRoot: HTMLElement, color: string | null | undefined): void;
    normalize(value: string | null | undefined): string | null;
    getLabel(value: string | null): string;
    renderPicker(colorValue: string | null | undefined, context: string): HTMLElement;
    updatePicker(picker: Element, colorValue: string | null | undefined): void;
    groups: ReadonlyArray<PromptColorGroup>;
}

export interface PromptGroup {
    heading: string | null;
    prompts: PromptRecord[];
}

export interface GroupResolvers {
    [DEFAULT_GROUP_KEY]: (list: PromptRecord[]) => PromptGroup[];
    date: (prompts: PromptRecord[]) => PromptGroup[];
    name: (prompts: PromptRecord[]) => PromptGroup[];
    color: (prompts: PromptRecord[]) => PromptGroup[];
}
