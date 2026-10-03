/* SoAI - Chat sketch modal page controller [frontend/assets/ts/pages/chat/controllers/modals/sketch/chatSketchModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { runModalSession } from '@core/modals/modalSession.ts';
import { CHAT_SKETCH_MODAL_ID } from '@features/chat/public.ts';
import type { ChatAttachmentActionPort, ChatExecutionActionPort } from '@pages/chat/controllers/actionhandlers/core/contracts.ts';
import { ChatSketchModalController } from '@pages/chat/controllers/modals/sketch/ChatSketchModalController.ts';
import type { ChatSketchModalHost } from '@pages/chat/controllers/modals/sketch/types.ts';

interface ChatSketchModalOpenHost {
    attachments: Pick<ChatAttachmentActionPort, 'sketchEnabled' | 'uploadSketch'>;
    execution: Pick<ChatExecutionActionPort, 'run'>;
    shared: Pick<ChatSketchModalHost, 'feedback'>;
}

const openChatSketchModal = (host: ChatSketchModalOpenHost): void => {
    if (!host.attachments.sketchEnabled()) {
        throw new Error('Chat sketch is not available');
    }
    const presenter = requireModalPresenter();
    if (presenter.isOpen(CHAT_SKETCH_MODAL_ID)) return;
    host.execution.run('chat:sketchModal', async () => {
        const file = await runModalSession<File | null>({
            presenter,
            modalId: CHAT_SKETCH_MODAL_ID,
            onAlreadyOpen: 'replace',
            initialResult: null,
            initialize: ({ modal, signal, setResult, close }) => {
                const controller = new ChatSketchModalController(
                    {
                        feedback: host.shared.feedback,
                        presenter,
                        submit: (sketch) => {
                            setResult(sketch);
                            close('submit');
                        }
                    },
                    modal,
                    signal
                );
                return { dispose: () => controller.dispose() };
            }
        });
        if (file === null) return;
        host.execution.run('chat:fileUpload', () => host.attachments.uploadSketch(file));
    });
};

export { openChatSketchModal };
