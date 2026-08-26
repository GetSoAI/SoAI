/* SoAI - Frontend application app lifecycle support [frontend/assets/ts/app/bootstrap/stages/appLifecycleSupport.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { requireDocument } from '@core/environment/public.ts';
import { sleepMs } from '@core/primitives/sleepMs.ts';

const querySelectorStrict = (selector: string): Element => {
    const element = dom.resolve(selector, requireDocument());
    if (!element) {
        throw new Error(`Expected element for selector: ${selector}`);
    }
    return element;
};

const sleep = async (delayMs: number): Promise<void> => {
    await sleepMs(delayMs);
};

export { querySelectorStrict, sleep };
