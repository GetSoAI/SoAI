/* SoAI - Conversation PDF export document stylesheet controller [frontend/assets/ts/pages/chat/controllers/chatmessagesendingcontroller/conversationExportPdfStyleController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { PDF_COLOR_ACCENT, PDF_COLOR_ASSISTANT_SURFACE, PDF_COLOR_EXACT_RULES, PDF_COLOR_HEADING, PDF_FONT_STACK_SANS, PDF_PAGE_RULE } from '@features/chat/public.ts';

const RADIUS_CARD = '10px';
const RADIUS_BLOCK = '8px';
const RADIUS_BLOCK_INNER = '7px';
const RADIUS_INLINE = '4px';
const BORDER = '1px solid #d2d9e1';
const BORDER_SOFT = '1px solid #e4e9ee';

const CONVERSATION_EXPORT_PDF_STYLE = `
${PDF_PAGE_RULE}
* { box-sizing: border-box; }
html {
  background: #eef1f4;
  color: #1e2329;
  font-family: ${PDF_FONT_STACK_SANS};
  font-size: 13px;
  line-height: 1.52;
  ${PDF_COLOR_EXACT_RULES}
}
body { margin: 0; background: #eef1f4; }
a { color: ${PDF_COLOR_ACCENT}; overflow-wrap: anywhere; text-decoration: none; }
a[href]::after { content: " (" attr(href) ")"; color: #687382; font-size: 10px; }
svg { max-width: 100%; height: auto; }
img, video { max-width: 100%; }
table { width: 100%; border-collapse: separate; border-spacing: 0; margin: 12px 0; break-inside: avoid; border: ${BORDER}; border-radius: ${RADIUS_BLOCK}; }
th, td { border: 0; border-right: ${BORDER}; border-bottom: ${BORDER}; padding: 6px 8px; vertical-align: top; }
tr > :last-child { border-right: 0; }
table > :last-child > tr:last-child > * { border-bottom: 0; }
table > :first-child > tr:first-child > :first-child { border-top-left-radius: ${RADIUS_BLOCK_INNER}; }
table > :first-child > tr:first-child > :last-child { border-top-right-radius: ${RADIUS_BLOCK_INNER}; }
table > :last-child > tr:last-child > :first-child { border-bottom-left-radius: ${RADIUS_BLOCK_INNER}; }
table > :last-child > tr:last-child > :last-child { border-bottom-right-radius: ${RADIUS_BLOCK_INNER}; }
th { background: #f3f6f8; color: #26313d; font-weight: 750; }
pre, code { font-family: ui-monospace, "SF Mono", "Cascadia Mono", "Segoe UI Mono", Consolas, "Liberation Mono", "DejaVu Sans Mono", monospace; }
pre { margin: 10px 0; padding: 10px 12px; border: ${BORDER}; border-radius: ${RADIUS_BLOCK}; background: #f7f9fb; color: #20262d; overflow-wrap: anywhere; white-space: pre-wrap; break-inside: auto; }
code { padding: 1px 4px; border-radius: ${RADIUS_INLINE}; background: #eef2f6; }
pre code { padding: 0; background: transparent; }
blockquote { margin: 10px 0; padding: 8px 12px; border: 1px solid #c6d2e0; border-radius: ${RADIUS_BLOCK}; background: #f2f6fb; color: #3f4c5a; }
.chat-export-pdf-shell { min-height: 100vh; background: #eef1f4; }
.chat-export-pdf-content { display: flex; flex-direction: column; gap: 14px; }
.chat-export-message {
  min-width: 0;
  padding: 12px 14px;
  border: ${BORDER};
  border-radius: ${RADIUS_CARD};
  background: #ffffff;
  box-shadow: 0 7px 20px rgba(30, 35, 41, 0.07);
  overflow-wrap: anywhere;
  orphans: 3;
  widows: 3;
}
.chat-export-message--user { background: #f3f8ec; border-color: #d4e3bd; }
.chat-export-message--assistant { background: ${PDF_COLOR_ASSISTANT_SURFACE}; border-color: #d9d9d9; }
.chat-export-message--compaction-boundary { background: #f5f7f2; border-color: #c9d7bd; }
.chat-export-message-header {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: baseline;
  justify-content: space-between;
  margin: 0 0 8px;
  padding-bottom: 7px;
  border-bottom: ${BORDER_SOFT};
  break-after: avoid;
  page-break-after: avoid;
}
.chat-export-message-role {
  color: #46576a;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.chat-export-message-time { color: #687382; font-size: 11px; }
.chat-export-message-metadata {
  display: flex;
  flex-wrap: wrap;
  gap: 5px 10px;
  margin: -2px 0 8px;
  color: #687382;
  font-size: 10px;
}
.chat-export-message-activity-metadata { margin: -5px 0 8px; color: #7d8996; font-size: 10px; }
.chat-export-compaction-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 0 0 8px;
  color: #607166;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.chat-export-compaction-fallback { color: #445466; }
.chat-export-message-body > :first-child { margin-top: 0; }
.chat-export-message-body > :last-child { margin-bottom: 0; }
.chat-export-message-body p { margin: 0 0 9px; }
.chat-export-message-body ul, .chat-export-message-body ol { margin: 8px 0 10px; padding-left: 22px; }
.chat-export-message-body li { margin: 3px 0; }
.chat-export-message-body h1, .chat-export-message-body h2, .chat-export-message-body h3, .chat-export-message-body h4 { margin: 14px 0 8px; color: ${PDF_COLOR_HEADING}; line-height: 1.24; break-after: avoid; }
.chat-export-message-body h1 { font-size: 22px; }
.chat-export-message-body h2 { font-size: 18px; }
.chat-export-message-body h3 { font-size: 15px; }
.chat-export-message-body h4 { font-size: 13px; }
.message-actions, .message-action-buttons, .code-copy-btn, .loading-spinner, .chat-inline-media-card__actions { display: none !important; }
.message-error { display: inline-flex; align-items: flex-start; gap: 8px; width: fit-content; max-width: 100%; padding: 8px 10px; border: 1px solid #f0b8b8; border-radius: ${RADIUS_BLOCK}; background: #fff5f5; color: #a62626; }
.message-error-icon { display: flex; flex: 0 0 auto; align-items: center; margin-top: 2px; line-height: 0; }
.message-error-text { min-width: 0; flex: 1 1 auto; line-height: 1.4; overflow-wrap: anywhere; }
.message-thinking, .inline-activity-details {
  display: block;
  margin: 8px 0;
  padding: 8px 10px;
  border: ${BORDER};
  border-radius: ${RADIUS_BLOCK};
  background: #f8fafc;
  color: #495869;
}
.chat-export-comparison-turn {
  padding: 12px;
  border: 1px solid #cad8d2;
  border-radius: ${RADIUS_CARD};
  background: #f4faf7;
  orphans: 3;
  widows: 3;
}
.chat-export-comparison-turn > header {
  margin: 0 0 10px;
  color: #244537;
  font-size: 12px;
  font-weight: 850;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  break-after: avoid;
  page-break-after: avoid;
}
.chat-export-comparison-variant { margin-top: 12px; padding-top: 12px; border-top: 1px solid #d6e3dd; }
.chat-export-comparison-variant:first-of-type { margin-top: 0; padding-top: 0; border-top: 0; }
.chat-export-comparison-variant-label { margin: 0 0 8px; color: #607166; font-size: 10px; font-weight: 850; letter-spacing: 0.06em; text-transform: uppercase; }
.chat-export-comparison-placeholder { padding: 10px; border: 1px dashed #a7b8ad; border-radius: ${RADIUS_BLOCK}; color: #607166; background: #ffffff; }
.chat-inline-media-card {
  display: grid;
  gap: 6px;
  max-width: 100%;
  margin: 5px 0;
  padding: 6px;
  border: ${BORDER};
  border-radius: ${RADIUS_BLOCK};
  background: #f9fbfd;
  break-inside: avoid;
}
.chat-export-inline-media-card--media {
  grid-template-columns: 104px minmax(0, 1fr);
  grid-template-rows: auto;
  align-items: start;
}
.chat-inline-media-card__footer { display: grid; gap: 2px; }
.chat-inline-media-card__title { color: #1d2733; font-weight: 800; overflow-wrap: anywhere; }
.chat-inline-media-card__subtitle, .chat-inline-media-card__reference-value { color: #687382; font-size: 10px; overflow-wrap: anywhere; }
.chat-inline-media-card__body { display: block; min-width: 0; }
.chat-export-inline-media-card--media .chat-inline-media-card__body { grid-column: 1; grid-row: 1; }
.chat-export-inline-media-card--media .chat-inline-media-card__footer { grid-column: 2; grid-row: 1; align-self: center; }
.chat-export-inline-media-card--media .chat-inline-media-card__excerpt { display: none; }
.chat-inline-media-card__media {
  display: grid;
  place-items: center;
  width: 100%;
  height: 62px;
  min-height: 0;
  max-height: 62px;
  border: ${BORDER};
  border-radius: ${RADIUS_BLOCK};
  background: #edf1f5;
  overflow: hidden;
}
.chat-inline-media-card__image, .chat-inline-media-card__media > video {
  display: block;
  width: auto;
  max-width: 100%;
  max-height: 62px;
  object-fit: contain;
  opacity: 1 !important;
}
.chat-inline-media-card__image--blurred-bg { display: none !important; }
.chat-inline-media-card__media > audio { width: 100%; opacity: 1 !important; }
.chat-inline-media-card__media-error[hidden] { display: none !important; }
.chat-inline-media-card__media--placeholder, .chat-inline-media-card__excerpt {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  padding: 8px;
  color: #445466;
  background: #ffffff;
  border: ${BORDER};
  border-radius: ${RADIUS_BLOCK};
}
.message-attachment-strip { display: flex; flex-wrap: wrap; gap: 7px; margin: 8px 0; }
.message-attachment-strip .file-preview-item { margin: 0; }
.file-preview-item {
  display: flex;
  gap: 8px;
  align-items: center;
  width: min(272px, 100%);
  margin: 7px 0;
  padding: 7px 8px;
  border: ${BORDER};
  border-radius: ${RADIUS_BLOCK};
  background: #f9fbfd;
  break-inside: avoid;
}
.file-preview-item > img { flex: 0 0 auto; width: 44px; height: 44px; border-radius: ${RADIUS_INLINE}; object-fit: cover; }
.file-preview-leading-icon { display: flex; flex: 0 0 auto; align-items: center; color: ${PDF_COLOR_ACCENT}; line-height: 0; }
.file-info { display: grid; gap: 2px; min-width: 0; }
.file-name { overflow: hidden; font-size: 12px; font-weight: 700; white-space: nowrap; text-overflow: ellipsis; }
.file-status { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; color: #687382; font-size: 10px; }
.chat-attachment-badge {
  padding: 1px 6px;
  border-radius: 999px;
  background: #eef2f6;
  color: #46576a;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
@media print {
  html, body, .chat-export-pdf-shell { background: #ffffff !important; }
  .chat-export-message, .chat-inline-media-card { box-shadow: none; }
}
`;

export { CONVERSATION_EXPORT_PDF_STYLE };
