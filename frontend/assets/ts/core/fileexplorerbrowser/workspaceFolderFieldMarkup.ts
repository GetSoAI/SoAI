/* SoAI - Shared workspace folder field markup [frontend/assets/ts/core/fileexplorerbrowser/workspaceFolderFieldMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import type { TrustedHtml } from '@core/security/public.ts';

type WorkspaceFolderFieldMarkupArguments = {
    pathInputId: string;
    changeButtonId: string;
    label: string;
    buttonLabel: string;
    action?: string;
    changeSurface?: boolean;
    fieldClassName?: string;
    rowClassName?: string;
    mainClassName?: string;
    actionClassName?: string;
    fieldAttributes?: TrustedHtml;
} & (
    | {
          status?: true;
          statusId: string;
          description: string;
      }
    | {
          status: false;
      }
);

const buildWorkspaceFolderFieldMarkup = (inputArguments: WorkspaceFolderFieldMarkupArguments): TrustedHtml => {
    const actionAttribute = inputArguments.action ? uiHtml` data-action="${uiAttr(inputArguments.action)}"` : uiHtml``;
    const changeSurfaceClassName = inputArguments.changeSurface === false ? '' : ' setting-change-surface';
    const fieldClassName = inputArguments.fieldClassName ? `form-group${changeSurfaceClassName} chat-config-span-2 ${inputArguments.fieldClassName}` : `form-group${changeSurfaceClassName} chat-config-span-2`;
    const statusMarkup = inputArguments.status === false ? uiHtml`` : uiHtml`<div id="${uiAttr(inputArguments.statusId)}" class="chat-configuration-hint">${inputArguments.description}</div>`;
    const rowClassName = inputArguments.rowClassName ? `form-row-split form-row-split--with-action ${inputArguments.rowClassName}` : 'form-row-split form-row-split--with-action';
    const mainClassName = inputArguments.mainClassName ? `form-col-main ${inputArguments.mainClassName}` : 'form-col-main';
    const actionClassName = inputArguments.actionClassName ? `form-col-action ${inputArguments.actionClassName}` : 'form-col-action';
    const fieldAttributes = inputArguments.fieldAttributes ?? uiHtml``;
    return uiHtml`<div class="${uiAttr(fieldClassName)}"${fieldAttributes}>
      <label for="${uiAttr(inputArguments.pathInputId)}">${inputArguments.label}</label>
      <div class="${uiAttr(rowClassName)}">
        <div class="${uiAttr(mainClassName)}">
          <input
            type="text"
            id="${uiAttr(inputArguments.pathInputId)}"
            class="form-input"
            readonly
          >
        </div>
        <div class="${uiAttr(actionClassName)}">
          <button
            type="button"
            id="${uiAttr(inputArguments.changeButtonId)}"
            class="ui-button"
            aria-label="${uiAttr(inputArguments.buttonLabel)}"
            data-tooltip="${uiAttr(inputArguments.buttonLabel)}"${actionAttribute}
          >${inputArguments.buttonLabel}</button>
        </div>
      </div>
      ${statusMarkup}
    </div>`;
};

export { buildWorkspaceFolderFieldMarkup };
