/* SoAI - Effective chat timeline send visual commit sequencing [frontend/assets/ts/pages/chat/controllers/chatmessagesendingcontroller/effectiveSendVisualCommitController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { awaitAnimationFrame } from '@core/runtime/animationFrames.ts';
import { clearComposerInput } from '@pages/chat/controllers/chatmessagesendingcontroller/effects.ts';

type EffectiveSendVisualCommitArguments = {
    composerTextForClearing: string | null;
    abortSignal: AbortSignal | null;
    renderCurrentConversation: () => Promise<void>;
    prepareComposerSurfaceForEffectiveSend?: (() => void) | undefined;
    onComposerSurfacePrepared?: (() => void) | undefined;
    onComposerCleared?: (() => void) | undefined;
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
        forceTimelineScrollToBottom: () => void;
    };
};

const commitEffectiveSendVisualState = async (host: EffectiveSendVisualCommitHost, inputArguments: EffectiveSendVisualCommitArguments): Promise<void> => {
    const shouldScrollToBottomAfterCommit = host.presentation.shouldAutoScrollAfterContentUpdate();
    if (inputArguments.prepareComposerSurfaceForEffectiveSend) {
        inputArguments.prepareComposerSurfaceForEffectiveSend();
        inputArguments.onComposerSurfacePrepared?.();
        host.presentation.flushDOMUpdates();
        await awaitAnimationFrame(inputArguments.abortSignal, 'Chat effective send visual commit aborted.');
    }
    const didClearComposerInput = inputArguments.composerTextForClearing === null ? false : clearComposerInput(host, inputArguments.composerTextForClearing);
    if (didClearComposerInput) {
        inputArguments.onComposerCleared?.();
    }
    host.presentation.flushDOMUpdates();
    await awaitAnimationFrame(inputArguments.abortSignal, 'Chat effective send visual commit aborted.');
    await inputArguments.renderCurrentConversation();
    host.presentation.flushDOMUpdates();
    if (shouldScrollToBottomAfterCommit) {
        host.presentation.forceTimelineScrollToBottom();
        host.presentation.flushDOMUpdates();
    }
    await awaitAnimationFrame(inputArguments.abortSignal, 'Chat effective send visual commit aborted.');
    host.presentation.flushDOMUpdates();
    await awaitAnimationFrame(inputArguments.abortSignal, 'Chat effective send visual commit aborted.');
};

export { commitEffectiveSendVisualState };
export type { EffectiveSendVisualCommitArguments, EffectiveSendVisualCommitHost };
