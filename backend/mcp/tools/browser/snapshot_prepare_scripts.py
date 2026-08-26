"""SoAI - Browser snapshot prepare/restore scripts [backend/mcp/tools/browser/snapshot_prepare_scripts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ()

SNAPSHOT_PREPARE_SCRIPT: str = """
    () => {
        const actionableRoles = new Set(['button', 'link', 'textbox', 'searchbox', 'checkbox', 'radio', 'combobox', 'option', 'tab', 'menuitem', 'switch', 'listitem', 'gridcell', 'treeitem']);
        const NONE = '__none__';

        const rememberOriginal = (el, attrName, markerName) => {
            if (el.hasAttribute(markerName)) {
                return;
            }
            const current = el.getAttribute(attrName);
            el.setAttribute(markerName, current === null ? NONE : String(current));
        };

        const ensureTempActionable = (el, labelPrefix) => {
            rememberOriginal(el, 'role', 'data-soai-temp-original-role');
            rememberOriginal(el, 'aria-label', 'data-soai-temp-original-aria-label');
            rememberOriginal(el, 'tabindex', 'data-soai-temp-original-tabindex');
            el.setAttribute('data-soai-temp-actionable', 'true');

            const currentRole = el.getAttribute('role');
            const normalizedRole = currentRole ? currentRole.toLowerCase() : '';
            if (!normalizedRole || !actionableRoles.has(normalizedRole)) {
                el.setAttribute('role', 'button');
            }
            const name = (el.innerText || '').trim() || el.getAttribute('aria-label') || el.id || el.title || 'item';
            el.setAttribute('aria-label', `${labelPrefix} ${name}`);
            if (!el.hasAttribute('tabindex')) {
                el.setAttribute('tabindex', '0');
            }
        };

        const draggableItems = Array.from(document.querySelectorAll('[draggable="true"]'));
        for (const el of draggableItems) {
            ensureTempActionable(el, '[draggable]');
        }

        const dropTargets = Array.from(document.querySelectorAll('[ondrop], [dropzone], [aria-dropeffect]'));
        for (const el of dropTargets) {
            ensureTempActionable(el, '[dropTarget]');
        }

        const hasConsentKeywords = (text) => {
            const keywords = ['accept', 'agree', 'consent', 'allow', 'i accept', 'ok', 'understand'];
            const lower = text.toLowerCase();
            return keywords.some(k => lower.includes(k));
        };
        const possible_consent_banner = Array.from(document.querySelectorAll('button, [role="button"]'))
            .some(btn => hasConsentKeywords(btn.innerText) && btn.offsetParent !== null);
        return { possible_consent_banner };
    }
    """

SNAPSHOT_RESTORE_SCRIPT: str = """
    () => {
        const items = Array.from(document.querySelectorAll('[data-soai-temp-actionable="true"]'));
        const NONE = '__none__';

        const restoreOriginal = (el, attrName, markerName) => {
            const stored = el.getAttribute(markerName);
            if (stored === null) {
                return;
            }
            if (stored === NONE) {
                el.removeAttribute(attrName);
            } else {
                el.setAttribute(attrName, stored);
            }
            el.removeAttribute(markerName);
        };

        for (const el of items) {
            restoreOriginal(el, 'role', 'data-soai-temp-original-role');
            restoreOriginal(el, 'aria-label', 'data-soai-temp-original-aria-label');
            restoreOriginal(el, 'tabindex', 'data-soai-temp-original-tabindex');
            el.removeAttribute('data-soai-temp-actionable');
        }
    }
    """
