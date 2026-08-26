/* SoAI - Settings page backup manager DOM contracts [frontend/assets/ts/pages/settings/controllers/backupmanager/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireClosestElement, requireTrimmedDataAttribute } from '@core/dom/attributes.ts';
import { resolveButtonList } from '@core/dom/typedElementResolver.ts';
import { narrowButton, optionalButton } from '@core/dom/narrowElement.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

type BackupManagerDomQueryHost = PageDomOwnerHost;

type BackupManagerDomRequiredQueryHost = BackupManagerDomQueryHost;

const requireHTMLElement = (host: BackupManagerDomRequiredQueryHost, selector: string, context?: Element): HTMLElement => host.pageDom.requireHTMLElement(selector, context);

const optionalHTMLElement = (host: BackupManagerDomQueryHost, selector: string, context?: Element): HTMLElement | null => host.pageDom.optionalHTMLElement(selector, context);

const requireButton = (host: BackupManagerDomRequiredQueryHost, selector: string, context?: Element): HTMLButtonElement => narrowButton(host.pageDom.require(selector, context), `Backup element "${selector}"`);

const optionalBackupButton = (host: BackupManagerDomQueryHost, selector: string, context?: Element): HTMLButtonElement | null => optionalButton(host.pageDom.optional(selector, context), `Backup element "${selector}"`);

const resolveButtons = (selector: string, root: Element): HTMLButtonElement[] => resolveButtonList(selector, root, `Backup selector "${selector}"`);

const requireBackupItemFromActionButton = (button: HTMLButtonElement): HTMLElement => {
    const item = requireClosestElement(button, '.settings-record-item', 'Backup action button');
    if (!(item instanceof HTMLElement)) {
        throw new TypeError('Backup action button must be nested under .settings-record-item');
    }
    return item;
};

const requireBackupValidFlag = (item: HTMLElement): boolean => {
    const value = requireTrimmedDataAttribute(item, 'backupValid', 'Backup item');
    if (value !== 'true' && value !== 'false') {
        throw new TypeError('Backup item must declare data-backup-valid="true|false"');
    }
    return value === 'true';
};

export { type BackupManagerDomQueryHost, type BackupManagerDomRequiredQueryHost, optionalBackupButton, optionalHTMLElement, requireBackupItemFromActionButton, requireBackupValidFlag, requireButton, requireHTMLElement, resolveButtons };
