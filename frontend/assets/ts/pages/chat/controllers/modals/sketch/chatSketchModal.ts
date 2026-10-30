/* SoAI - Chat sketch modal page controller [frontend/assets/ts/pages/chat/controllers/modals/sketch/chatSketchModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { runModalSession } from '@core/modals/modalSession.ts';
import { i18n } from '@core/i18n/index.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { CHAT_SKETCH_MODAL_ID } from '@features/chat/public.ts';
import type { ChatAttachmentActionPort, ChatExecutionActionPort } from '@pages/chat/controllers/actionhandlers/core/contracts.ts';
import { ChatSketchModalController } from '@pages/chat/controllers/modals/sketch/ChatSketchModalController.ts';
import type { ChatSketchModalHost } from '@pages/chat/controllers/modals/sketch/types.ts';

interface ChatSketchModalOpenHost {
    attachments: Pick<ChatAttachmentActionPort, 'sketchEnabled' | 'uploadSketch' | 'captureIntake'>;
    execution: Pick<ChatExecutionActionPort, 'run'>;
    shared: Pick<ChatSketchModalHost, 'feedback'> & { signal(): AbortSignal | null };
}

const openChatSketchModal = (host: ChatSketchModalOpenHost): void => {
    if (!host.attachments.sketchEnabled()) {
        throw new Error('Chat sketch is not available');
    }
    const presenter = requireModalPresenter();
    if (presenter.isOpen(CHAT_SKETCH_MODAL_ID)) return;
    let intake = host.attachments.captureIntake();
    host.execution.run('chat:sketchModal', async () => {
        const file = await runModalSession<File | null>({
            presenter,
            modalId: CHAT_SKETCH_MODAL_ID,
            signal: host.shared.signal() ?? undefined,
            onAlreadyOpen: 'replace',
            initialResult: null,
            initialize: ({ modal, signal, setResult, close }) => {
                const controller = new ChatSketchModalController(
                    {
                        feedback: host.shared.feedback,
                        presenter,
                        submit: async (sketch) => {
                            if (signal.aborted) return;
                            if (!intake.scope.isCurrent()) {
                                const candidate = host.attachments.captureIntake();
                                const confirmed = await requireDialogsService().showConfirmation({
                                    signal,
                                    title: i18n.t('chat.sketch.title'),
                                    message: i18n.t('chat.sketch.draftChangedConfirm'),
                                    confirmText: i18n.t('chat.sketch.attach'),
                                    variant: 'warning'
                                });
                                if (!confirmed || signal.aborted) return;
                                if (!candidate.scope.isCurrent()) {
                                    host.shared.feedback.show(i18n.t('chat.sketch.draftChangedAgain'), 'warning');
                                    return;
                                }
                                intake = candidate;
                            }
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
        if (file === null || !intake.scope.isCurrent()) return;
        host.execution.run('chat:fileUpload', () => host.attachments.uploadSketch(file, intake));
    });
};

export { openChatSketchModal };
