/**
 * Client-side PDF generation via print dialog.
 * Opens a new window with the formatted dossier and triggers the browser's
 * built-in print-to-PDF dialog (Ctrl+P / Cmd+P).
 */
export async function generateDossierPdf(targetName: string, dossierMd: string): Promise<void> {
  const { default: markdownit } = await import("markdown-it");
  const md = markdownit({ html: true, linkify: true, typographer: true });
  const htmlBody = md.render(dossierMd);

  const html = `<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <title>Dossier — ${escapeHtml(targetName)}</title>
  <style>
    @page {
      size: A4;
      margin: 2cm 2.5cm;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: "Georgia", "Times New Roman", serif;
      font-size: 11pt;
      line-height: 1.6;
      color: #1a1a1a;
      max-width: 100%;
    }
    h1 { font-size: 22pt; margin: 0 0 8pt; font-weight: 700; }
    h2 { font-size: 15pt; margin: 24pt 0 8pt; font-weight: 700; border-bottom: 1px solid #ccc; padding-bottom: 4pt; }
    h3 { font-size: 12pt; margin: 16pt 0 6pt; font-weight: 600; }
    p { margin: 6pt 0; }
    blockquote {
      border-left: 3px solid #DA7756;
      padding-left: 12pt;
      margin: 8pt 0;
      color: #555;
      font-style: italic;
    }
    ul, ol { margin: 6pt 0; padding-left: 20pt; }
    li { margin: 3pt 0; }
    strong { font-weight: 700; }
    a { color: #DA7756; text-decoration: underline; }
    table {
      width: 100%;
      border-collapse: collapse;
      margin: 10pt 0;
      font-size: 9pt;
    }
    th, td {
      border: 1px solid #ddd;
      padding: 5pt 8pt;
      text-align: left;
    }
    th { background: #f5f5f0; font-weight: 600; }
    hr { border: none; border-top: 1px solid #ccc; margin: 16pt 0; }
    code {
      font-family: "Courier New", monospace;
      font-size: 9pt;
      background: #f5f5f0;
      padding: 1pt 3pt;
      border-radius: 2pt;
    }
    pre {
      background: #f5f5f0;
      padding: 10pt;
      border-radius: 4pt;
      overflow: auto;
      font-size: 8pt;
      margin: 8pt 0;
    }
    .header-bar {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      border-bottom: 2px solid #DA7756;
      padding-bottom: 8pt;
      margin-bottom: 16pt;
    }
    .header-bar .logo {
      font-family: sans-serif;
      font-size: 9pt;
      text-transform: uppercase;
      letter-spacing: 2pt;
      color: #DA7756;
      font-weight: 700;
    }
    .header-bar .date {
      font-family: monospace;
      font-size: 8pt;
      color: #888;
    }
    .footer {
      margin-top: 32pt;
      padding-top: 8pt;
      border-top: 1px solid #ccc;
      font-family: monospace;
      font-size: 7pt;
      text-transform: uppercase;
      letter-spacing: 1pt;
      color: #999;
      text-align: center;
    }
    @media print {
      body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    }
  </style>
</head>
<body>
  <div class="header-bar">
    <span class="logo">Sabueso · Dossier Público</span>
    <span class="date">${new Date().toLocaleDateString("es-PE", { year: "numeric", month: "long", day: "numeric" })}</span>
  </div>
  ${htmlBody}
  <div class="footer">
    Generado por Sabueso · hack@latam 2026 · ${new Date().toISOString()}
  </div>
  <script>window.onload = function() { window.print(); }<\/script>
</body>
</html>`;

  const blob = new Blob([html], { type: "text/html" });
  const url = URL.createObjectURL(blob);
  const win = window.open(url, "_blank");
  if (win) {
    win.onafterprint = () => {
      URL.revokeObjectURL(url);
    };
  }
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

function escapeHtml(str: string): string {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
