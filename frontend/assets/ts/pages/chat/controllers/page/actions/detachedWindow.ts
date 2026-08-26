/* SoAI - Chat page control layer actions detached window [frontend/assets/ts/pages/chat/controllers/page/actions/detachedWindow.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { closeDetachedRuntimeWindowsByPage } from '@core/runtimeenv/public.ts';
import { openChatDetachedWindow, type DetachedWindowHost } from '@pages/chat/controllers/detached/chatDetachedWindow.ts';

const openDetachedChatWindow = (host: DetachedWindowHost): void => {
    closeDetachedRuntimeWindowsByPage('chat');
    openChatDetachedWindow(host);
};

export { openDetachedChatWindow };
