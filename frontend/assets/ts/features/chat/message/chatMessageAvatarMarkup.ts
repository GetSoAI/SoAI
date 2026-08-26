/* SoAI - Chat feature message avatar markup [frontend/assets/ts/features/chat/message/chatMessageAvatarMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { CHAT_ICON_SIZE_LG } from '@features/chat/chatConstants.ts';
import { CHAT_MESSAGE_ROLE_ICONS } from '@features/chat/message/constants.ts';

interface ChatMessageAvatarMarkupDependencies {
    escapeAttribute: (value: string) => string;
    escapeHtml: (value: string) => string;
    getAssistantAvatarUrl: () => string | null;
    getUserAvatarUrl: () => string | null;
    getIconHtml: (name: IconName, options?: IconOptions) => string;
}

const resolveRoleIconName = (role: string): IconName => {
    const roleKey = String(role ?? '')
        .trim()
        .toLowerCase();
    return CHAT_MESSAGE_ROLE_ICONS[roleKey] ? CHAT_MESSAGE_ROLE_ICONS[roleKey] : 'ellipsis';
};

interface RoleBadgeTextDependencies {
    escapeHtml: (value: string) => string;
}

const renderRoleBadgeText = (dependencies: RoleBadgeTextDependencies, senderLabel: string): string => {
    return `<span class="message-role-badge"><span class="message-role-badge-text">${dependencies.escapeHtml(senderLabel)}</span></span>`;
};

const resolveAvatarUrl = (dependencies: ChatMessageAvatarMarkupDependencies, role: string): string | null => {
    return role === 'assistant' ? dependencies.getAssistantAvatarUrl() : role === 'user' ? dependencies.getUserAvatarUrl() : null;
};

const isUploadableDefaultAvatar = (role: string, avatarUrl: string | null): boolean => {
    return avatarUrl === null && (role === 'assistant' || role === 'user');
};

const renderUploadableAvatarButton = (dependencies: ChatMessageAvatarMarkupDependencies, role: string, roleIconName: IconName): string => {
    const uploadAction = role === 'assistant' ? 'chat:upload-assistant-avatar' : 'chat:upload-user-avatar';
    const uploadLabel = dependencies.escapeAttribute(role === 'assistant' ? i18n.t('chat.configuration.assistantAvatarUploadLabel') : i18n.t('chat.configuration.userAvatarUploadLabel'));
    const defaultIconHtml = dependencies.getIconHtml(roleIconName, CHAT_ICON_SIZE_LG);
    const uploadIconHtml = dependencies.getIconHtml('avatar-upload', CHAT_ICON_SIZE_LG);
    return `<button type="button" class="message-avatar-icon-hit-target message-avatar-icon--uploadable" data-action="${uploadAction}" aria-label="${uploadLabel}" data-tooltip="${uploadLabel}">` + `<span class="message-avatar-icon-default" aria-hidden="true">${defaultIconHtml}</span>` + `<span class="message-avatar-icon-upload" aria-hidden="true">${uploadIconHtml}</span>` + `</button>`;
};

const renderAvatarContent = (dependencies: ChatMessageAvatarMarkupDependencies, role: string, roleIconName: IconName, avatarUrl: string | null): string => {
    if (avatarUrl) {
        const sanitizedSrc = dependencies.escapeAttribute(avatarUrl);
        return `<img src="${sanitizedSrc}" alt="" class="chat-avatar-image">`;
    }
    if (isUploadableDefaultAvatar(role, avatarUrl)) {
        return renderUploadableAvatarButton(dependencies, role, roleIconName);
    }
    return dependencies.getIconHtml(roleIconName, CHAT_ICON_SIZE_LG);
};

const renderChatMessageAvatarContainer = (dependencies: ChatMessageAvatarMarkupDependencies, role: string, senderLabel: string): string => {
    const roleIconName = resolveRoleIconName(role);
    const avatarTitle = role === 'user' || role === 'assistant' ? ` data-tooltip="${dependencies.escapeAttribute(senderLabel)}"` : '';
    const avatarUrl = resolveAvatarUrl(dependencies, role);
    const avatarHtml = renderAvatarContent(dependencies, role, roleIconName, avatarUrl);
    const iconHiddenAttribute = isUploadableDefaultAvatar(role, avatarUrl) ? '' : ' aria-hidden="true"';
    const avatarLabelHtml = role === 'assistant' || role === 'user' ? `<span class="message-avatar-label">${renderRoleBadgeText(dependencies, senderLabel)}</span>` : '';
    return `<div class="message-avatar"${avatarTitle}><span class="message-avatar-icon"${iconHiddenAttribute}>${avatarHtml}</span>${avatarLabelHtml}</div>`;
};

export { renderChatMessageAvatarContainer, renderRoleBadgeText };
export type { ChatMessageAvatarMarkupDependencies };
