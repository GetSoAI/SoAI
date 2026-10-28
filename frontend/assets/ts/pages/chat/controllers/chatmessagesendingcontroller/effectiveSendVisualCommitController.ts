/* SoAI - Effective chat timeline send visual commit sequencing [frontend/assets/ts/pages/chat/controllers/chatmessagesendingcontroller/effectiveSendVisualCommitController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { awaitPresentationFrame } from '@core/runtime/animationFrames.ts';
import { throwIfAborted } from '@core/errors/abort.ts';
import { clearComposerInput } from '@pages/chat/controllers/chatmessagesendingcontroller/effects.ts';

type EffectiveSendVisualCommitArguments = {
    scrollToBottomOnSend?: boolean;
    composerTextForClearing: string | null;
    abortSignal: AbortSignal | null;
    renderCurrentConversation: () => Promise<void>;
    prepareComposerSurfaceForEffectiveSend?: (() => void) | undefined;
};

type EffectiveSendVisualCommitHost = {
    composer: {
        getChatInput: () => HTMLTextAreaElement | null;
        setUIValue: (element: Element, value: string, options?: { attribute?: string }) => void;
        resizeChatInput: (element: Element) => void;
        noteChatInputDraftChanged: (value: string) => void;
    };
    presentation: {
        flushDOMUpdates: () => void;
        shouldAutoScrollAfterContentUpdate: () => boolean;
        forceTimelineScrollToBottom: (behavior?: ScrollBehavior) => void;
    };
};

const commitEffectiveSendVisualState = async (host: EffectiveSendVisualCommitHost, inputArguments: EffectiveSendVisualCommitArguments): Promise<void> => {
    throwIfAborted(inputArguments.abortSignal);
    const shouldScrollToBottomAfterCommit = host.presentation.shouldAutoScrollAfterContentUpdate();
    if (inputArguments.prepareComposerSurfaceForEffectiveSend) {
        inputArguments.prepareComposerSurfaceForEffectiveSend();
        host.presentation.flushDOMUpdates();
        await awaitPresentationFrame(inputArguments.abortSignal, 'Chat effective send visual commit aborted.');
    }
    throwIfAborted(inputArguments.abortSignal);
    if (inputArguments.composerTextForClearing !== null) {
        clearComposerInput(host, inputArguments.composerTextForClearing);
    }
    host.presentation.flushDOMUpdates();
    await awaitPresentationFrame(inputArguments.abortSignal, 'Chat effective send visual commit aborted.');
    throwIfAborted(inputArguments.abortSignal);
    await inputArguments.renderCurrentConversation();
    throwIfAborted(inputArguments.abortSignal);
    host.presentation.flushDOMUpdates();
    if (inputArguments.scrollToBottomOnSend || shouldScrollToBottomAfterCommit) {
        host.presentation.forceTimelineScrollToBottom(inputArguments.scrollToBottomOnSend ? 'smooth' : 'instant');
        host.presentation.flushDOMUpdates();
    }
    await awaitPresentationFrame(inputArguments.abortSignal, 'Chat effective send visual commit aborted.');
    throwIfAborted(inputArguments.abortSignal);
    host.presentation.flushDOMUpdates();
    await awaitPresentationFrame(inputArguments.abortSignal, 'Chat effective send visual commit aborted.');
};

export { commitEffectiveSendVisualState };
export type { EffectiveSendVisualCommitArguments, EffectiveSendVisualCommitHost };
