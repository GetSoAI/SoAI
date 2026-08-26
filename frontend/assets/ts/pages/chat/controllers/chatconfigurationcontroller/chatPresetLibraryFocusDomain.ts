/* SoAI - Chat preset library keyboard focus continuity [frontend/assets/ts/pages/chat/controllers/chatconfigurationcontroller/chatPresetLibraryFocusDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { CHAT_ACTIONS } from '@features/chat/public.ts';
import type { ChatPresetEditorDraft } from '@pages/chat/controllers/chatconfigurationcontroller/contracts.ts';

type ChatPresetLibraryFocusSnapshot = Readonly<{ type: 'input'; id: string; start: number | null; end: number | null }> | Readonly<{ type: 'action'; action: string; presetId: string | null; rowIndex: number }>;
type ChatPresetEditorFocusTarget = Readonly<{ mode: ChatPresetEditorDraft['mode']; targetId: string | null }>;

const captureChatPresetLibraryFocus = (root: Element): ChatPresetLibraryFocusSnapshot | null => {
    const active = root.ownerDocument.activeElement;
    if (active instanceof HTMLInputElement && active.id) return { type: 'input', id: active.id, start: active.selectionStart, end: active.selectionEnd };
    if (!(active instanceof HTMLElement) || !root.contains(active)) return null;
    const action = active.dataset['action'];
    if (!action) return null;
    const row = active.closest<HTMLElement>('.chat-preset-row');
    const rows = dom.resolveAll('.chat-preset-row', root).filter((element): element is HTMLElement => element instanceof HTMLElement);
    return { type: 'action', action, presetId: row?.dataset['presetId'] ?? null, rowIndex: row ? rows.indexOf(row) : 0 };
};

const restoreChatPresetLibraryFocus = (root: Element, snapshot: ChatPresetLibraryFocusSnapshot | null): void => {
    if (!snapshot) return;
    if (snapshot.type === 'input') {
        const candidate = root.ownerDocument.getElementById(snapshot.id);
        const element = candidate && root.contains(candidate) ? candidate : null;
        if (!(element instanceof HTMLInputElement)) return;
        element.focus({ preventScroll: true });
        if (snapshot.start !== null && snapshot.end !== null) element.setSelectionRange(snapshot.start, snapshot.end);
        return;
    }
    const rows = dom.resolveAll('.chat-preset-row', root).filter((element): element is HTMLElement => element instanceof HTMLElement);
    const row = rows.find((candidate) => candidate.dataset['presetId'] === snapshot.presetId) ?? rows[Math.min(snapshot.rowIndex, Math.max(rows.length - 1, 0))];
    const action = row ? dom.resolveAll('[data-action]', row).find((candidate): candidate is HTMLElement => candidate instanceof HTMLElement && candidate.dataset['action'] === snapshot.action && !('disabled' in candidate && candidate.disabled)) : null;
    const fallback = dom.resolve(`[data-action="${CHAT_ACTIONS.NEW_PRESET}"]`, root);
    (action ?? (fallback instanceof HTMLElement ? fallback : null))?.focus({ preventScroll: true });
};

const readChatPresetEditorFocusTarget = (editor: HTMLElement): ChatPresetEditorFocusTarget | null => {
    const mode = editor.dataset['presetEditorMode'];
    if (mode !== 'create' && mode !== 'rename' && mode !== 'replace') return null;
    return { mode, targetId: editor.dataset['presetEditorTargetId'] ?? null };
};

const focusChatPresetEditorTransition = (root: Element, previous: ChatPresetEditorFocusTarget | null, current: ChatPresetEditorDraft | null): boolean => {
    if (!previous && current) {
        const input = dom.resolve('[data-chat-preset-editor-name="true"]', root);
        if (input instanceof HTMLInputElement) input.focus({ preventScroll: true });
        return true;
    }
    if (!previous || current) return false;
    const action = previous.mode === 'create' ? CHAT_ACTIONS.NEW_PRESET : previous.mode === 'rename' ? CHAT_ACTIONS.RENAME_PRESET : CHAT_ACTIONS.REPLACE_PRESET;
    const candidates = dom.resolveAll(`[data-action="${action}"]`, root).filter((element): element is HTMLElement => element instanceof HTMLElement);
    const target = candidates.find((element) => previous.targetId === null || element.dataset['presetId'] === previous.targetId) ?? candidates[0];
    const fallback = dom.resolve(`[data-action="${CHAT_ACTIONS.NEW_PRESET}"]`, root);
    (target ?? (fallback instanceof HTMLElement ? fallback : null))?.focus({ preventScroll: true });
    return true;
};

export { captureChatPresetLibraryFocus, focusChatPresetEditorTransition, readChatPresetEditorFocusTarget, restoreChatPresetLibraryFocus };
