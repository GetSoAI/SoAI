/* SoAI - Frontend chat sketch modal definition [frontend/assets/ts/features/chat/sketch/definition.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderModalFooterActionButton, renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import type { ModalDefinition } from '@core/modals/modalPresenter.ts';
import { renderModalBody, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';
import { createModalElement } from '@core/modals/scaffoldDom.ts';
import { modalUiId, modalUiSelector } from '@core/modals/uiIds.ts';
import { renderLabelAttributes, type TrustedHtml } from '@core/security/public.ts';
import { joinUiHtml, uiAttr, uiAttributes, uiHtml, uiText } from '@core/security/uiHtml.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { CHAT_SKETCH_MODAL_ID } from '@features/chat/modals/constants.ts';
import { CHAT_SKETCH_ACTIONS, type ChatSketchAction } from '@features/chat/sketch/actions.ts';
import { CHAT_SKETCH_CANVAS_HEIGHT, CHAT_SKETCH_CANVAS_WIDTH, CHAT_SKETCH_COLORS, CHAT_SKETCH_DEFAULT_COLOR, CHAT_SKETCH_DEFAULT_TOOL, CHAT_SKETCH_SIZE_MAX, CHAT_SKETCH_SIZE_MIN, CHAT_SKETCH_TOOLS, requireChatSketchTool, type ChatSketchColorId, type ChatSketchToolType } from '@features/chat/sketch/sketchCatalog.ts';

const CHAT_SKETCH_ICON_OPTIONS = Object.freeze({ size: 18, strokeWidth: 1.5 });
const CHAT_SKETCH_SPECTRUM_IDS: ReadonlySet<ChatSketchColorId> = new Set(['red', 'orange', 'yellow', 'green', 'teal', 'blue', 'purple']);
const CHAT_SKETCH_SPECTRUM_STOPS = CHAT_SKETCH_COLORS.filter((color) => CHAT_SKETCH_SPECTRUM_IDS.has(color.id)).map((color) => color.value);
const CHAT_SKETCH_SPECTRUM = `conic-gradient(${[...CHAT_SKETCH_SPECTRUM_STOPS, ...CHAT_SKETCH_SPECTRUM_STOPS.slice(0, 1)].join(', ')})`;

const resolveChatSketchToolLabel = (type: ChatSketchToolType): string => {
    if (type === 'pen') return i18n.t('chat.sketch.tools.pen');
    if (type === 'brush') return i18n.t('chat.sketch.tools.brush');
    if (type === 'highlighter') return i18n.t('chat.sketch.tools.highlighter');
    if (type === 'eraser') return i18n.t('chat.sketch.tools.eraser');
    if (type === 'line') return i18n.t('chat.sketch.tools.line');
    if (type === 'rectangle') return i18n.t('chat.sketch.tools.rectangle');
    return i18n.t('chat.sketch.tools.ellipse');
};

const resolveChatSketchColorLabel = (id: ChatSketchColorId): string => {
    if (id === 'black') return i18n.t('chat.sketch.colors.black');
    if (id === 'grey') return i18n.t('chat.sketch.colors.grey');
    if (id === 'red') return i18n.t('chat.sketch.colors.red');
    if (id === 'orange') return i18n.t('chat.sketch.colors.orange');
    if (id === 'yellow') return i18n.t('chat.sketch.colors.yellow');
    if (id === 'green') return i18n.t('chat.sketch.colors.green');
    if (id === 'teal') return i18n.t('chat.sketch.colors.teal');
    if (id === 'blue') return i18n.t('chat.sketch.colors.blue');
    if (id === 'purple') return i18n.t('chat.sketch.colors.purple');
    return i18n.t('chat.sketch.colors.brown');
};

const renderIconButton = (options: { id: string; action: ChatSketchAction; iconName: IconName; label: string; className: string; attributes: Readonly<Record<string, string | boolean>> }): TrustedHtml => uiHtml`<button type="button" id="${uiAttr(options.id)}" class="ui-icon-button ${uiAttr(options.className)}" data-action="${uiAttr(options.action)}"${uiAttributes(options.attributes)} ${renderLabelAttributes(options.label)}>${getIconSync(options.iconName, CHAT_SKETCH_ICON_OPTIONS)}</button>`;

const CHAT_SKETCH_TOOL_SEPARATOR = uiHtml`<span class="chat-sketch-toolbar__separator" aria-hidden="true"></span>`;

const renderToolButtons = (modalId: string): TrustedHtml =>
    joinUiHtml(
        CHAT_SKETCH_TOOLS.map((tool, index) => {
            const button = renderIconButton({
                id: modalUiId(modalId, `tool-${tool.type}`),
                action: CHAT_SKETCH_ACTIONS.SELECT_TOOL,
                iconName: tool.iconName,
                label: resolveChatSketchToolLabel(tool.type),
                className: 'chat-sketch-tool',
                attributes: { 'data-sketch-tool': tool.type, 'aria-pressed': String(tool.type === CHAT_SKETCH_DEFAULT_TOOL) }
            });
            const previous = CHAT_SKETCH_TOOLS[index - 1];
            return previous !== undefined && previous.section !== tool.section ? joinUiHtml([CHAT_SKETCH_TOOL_SEPARATOR, button]) : button;
        })
    );

const renderColorSwatches = (): TrustedHtml => joinUiHtml(CHAT_SKETCH_COLORS.map((color) => uiHtml`<button type="button" class="chat-sketch-swatch" data-action="${uiAttr(CHAT_SKETCH_ACTIONS.SELECT_COLOR)}" data-sketch-color="${uiAttr(color.value)}" style="--chat-sketch-swatch-color:${uiAttr(color.value)};" aria-pressed="${uiAttr(String(color.value === CHAT_SKETCH_DEFAULT_COLOR))}" ${renderLabelAttributes(resolveChatSketchColorLabel(color.id))}></button>`));

const renderHistoryButtons = (modalId: string): TrustedHtml => {
    const attributes = { disabled: true, 'aria-disabled': 'true' };
    return joinUiHtml([renderIconButton({ id: modalUiId(modalId, 'undo'), action: CHAT_SKETCH_ACTIONS.UNDO, iconName: 'undo', label: i18n.t('chat.sketch.undo'), className: 'chat-sketch-history', attributes }), renderIconButton({ id: modalUiId(modalId, 'redo'), action: CHAT_SKETCH_ACTIONS.REDO, iconName: 'redo', label: i18n.t('chat.sketch.redo'), className: 'chat-sketch-history', attributes })]);
};

const renderWorkbench = (modalId: string): TrustedHtml => {
    const colorId = modalUiId(modalId, 'color');
    const sizeId = modalUiId(modalId, 'size');
    const defaultSize = requireChatSketchTool(CHAT_SKETCH_DEFAULT_TOOL).defaultSize;
    return uiHtml`
        <div class="chat-sketch-workbench">
            <div class="chat-sketch-toolbar">
                <div class="chat-sketch-toolbar__group" role="group" aria-label="${uiAttr(i18n.t('chat.sketch.toolsLabel'))}">${renderToolButtons(modalId)}</div>
                <div class="chat-sketch-toolbar__group chat-sketch-palette" role="group" aria-label="${uiAttr(i18n.t('chat.sketch.colorsLabel'))}">
                    <div class="chat-sketch-swatches">${renderColorSwatches()}</div>
                    <input type="color" id="${uiAttr(colorId)}" class="chat-sketch-color-input" value="${uiAttr(CHAT_SKETCH_DEFAULT_COLOR)}" style="--chat-sketch-spectrum:${uiAttr(CHAT_SKETCH_SPECTRUM)};" ${renderLabelAttributes(i18n.t('chat.sketch.customColor'))}>
                </div>
                <div class="chat-sketch-toolbar__group chat-sketch-size">
                    <span id="${uiAttr(modalUiId(modalId, 'size-preview'))}" class="chat-sketch-size-preview" aria-hidden="true"></span>
                    <input type="range" id="${uiAttr(sizeId)}" class="ui-range chat-sketch-size-input" min="${uiAttr(String(CHAT_SKETCH_SIZE_MIN))}" max="${uiAttr(String(CHAT_SKETCH_SIZE_MAX))}" step="1" value="${uiAttr(String(defaultSize))}" ${renderLabelAttributes(i18n.t('chat.sketch.size'))}>
                    <output id="${uiAttr(modalUiId(modalId, 'size-value'))}" class="chat-sketch-size-value" for="${uiAttr(sizeId)}">${uiText(String(defaultSize))}</output>
                </div>
                <div class="chat-sketch-toolbar__group chat-sketch-toolbar__history">${renderHistoryButtons(modalId)}</div>
            </div>
            <div id="${uiAttr(modalUiId(modalId, 'stage'))}" class="chat-sketch-stage">
                <div class="chat-sketch-frame">
                    <canvas id="${uiAttr(modalUiId(modalId, 'canvas'))}" class="chat-sketch-canvas" width="${uiAttr(String(CHAT_SKETCH_CANVAS_WIDTH))}" height="${uiAttr(String(CHAT_SKETCH_CANVAS_HEIGHT))}" role="img" aria-label="${uiAttr(i18n.t('chat.sketch.canvasLabel'))}" data-sketch-tool="${uiAttr(CHAT_SKETCH_DEFAULT_TOOL)}"></canvas>
                    <button type="button" id="${uiAttr(modalUiId(modalId, 'resize'))}" class="chat-sketch-resize" ${renderLabelAttributes(i18n.t('chat.sketch.resize'))}>${getIconSync('resize-corner', CHAT_SKETCH_ICON_OPTIONS)}</button>
                </div>
            </div>
        </div>
    `;
};

const CHAT_SKETCH_MODAL_DEFINITION: ModalDefinition = Object.freeze({
    id: CHAT_SKETCH_MODAL_ID,
    layout: 'xl',
    initialFocusSelector: modalUiSelector(CHAT_SKETCH_MODAL_ID, `tool-${CHAT_SKETCH_DEFAULT_TOOL}`),
    createElement: (): HTMLElement => {
        const modalId = CHAT_SKETCH_MODAL_ID;
        const closeLabel = i18n.t('common.close');
        const header = renderStandardModalHeader({ modalId, title: i18n.t('chat.sketch.title'), description: i18n.t('chat.sketch.description'), closeLabel });
        const body = renderModalBody(renderWorkbench(modalId), { className: 'chat-sketch-modal-body' });
        const footer = renderSplitModalFooter({
            left: renderModalFooterCloseButton({ modalId, text: closeLabel }),
            right: joinUiHtml([renderModalFooterActionButton({ id: modalUiId(modalId, 'clear'), action: CHAT_SKETCH_ACTIONS.CLEAR, text: i18n.t('chat.sketch.clear'), variant: 'danger', disabled: true }), renderModalFooterActionButton({ id: modalUiId(modalId, 'attach'), action: CHAT_SKETCH_ACTIONS.ATTACH, text: i18n.t('chat.sketch.attach'), variant: 'success', disabled: true })])
        });
        return createModalElement({ id: modalId, rootAttributes: { 'data-page-scope': 'chat' }, header, body, footer });
    }
});

export { CHAT_SKETCH_MODAL_DEFINITION };
