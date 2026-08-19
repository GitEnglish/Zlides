const fs = require('fs');

let slideServer = fs.readFileSync('slide_server.py', 'utf-8');
slideServer = slideServer.replace('base += "\\n\\nCRITICAL COLOR PALETTE INSTRUCTIONS:\\n"',
    'base += "\\n\\nCRITICAL INSTRUCTIONS:\\n- DO NOT add @media print rules that override background colors (e.g. body { background: white !important }). The background color MUST be preserved exactly when printing.\\n\\nCRITICAL COLOR PALETTE INSTRUCTIONS:\\n"');
fs.writeFileSync('slide_server.py', slideServer);

let appSvelte = fs.readFileSync('frontend_svelte/src/App.svelte', 'utf-8');

// Add editor state
appSvelte = appSvelte.replace("let isUploading = false;", "let isUploading = false;\n  let isEditingHtml = false;\n  let editorHtml = '';");

// Replace the export bar with an export + edit bar
const exportHtmlBar = `
        <button class="text-xs px-3 py-1 bg-ge-bg border border-ge-border rounded hover:bg-ge-border transition-colors" on:click={() => {
          if (!slides.length) {
            slides = [{ html: '<html><body><div class="p-8"><h1>Paste your HTML here</h1></div></body></html>' }];
            currentSlideIndex = 0;
          }
          isEditingHtml = !isEditingHtml;
          if (isEditingHtml) {
            editorHtml = slides[currentSlideIndex].html;
          } else {
            slides[currentSlideIndex].html = editorHtml;
            const combined = [editorHtml].join('')
                .replace(/\\\\n/g, '\\n').replace(/\\\\"/g, '"');
            try {
                const doc = iframeElement?.contentDocument;
                if (doc && doc.body && doc.body.innerHTML.length > 0) {
                    const prevScroll = doc.documentElement.scrollTop || doc.body.scrollTop;
                    doc.body.innerHTML = combined;
                    doc.documentElement.scrollTop = doc.body.scrollTop = prevScroll;
                } else {
                    iframeSrcDoc = combined;
                }
            } catch(e) {
                iframeSrcDoc = combined;
            }
          }
        }}>{isEditingHtml ? 'Apply HTML' : 'Edit / Paste HTML'}</button>
        <button class="text-xs px-3 py-1 bg-ge-bg border border-ge-border rounded hover:bg-ge-border transition-colors" on:click={() => {
          if (!slides.length) return;
          const html = slides[currentSlideIndex].html;
          const blob = new Blob([html], { type: 'text/html' });
          const link = document.createElement('a');
          link.download = \`slide_\${currentSlideIndex + 1}.html\`;
          link.href = URL.createObjectURL(blob);
          link.click();
          URL.revokeObjectURL(link.href);
        }}>Export HTML</button>`;

appSvelte = appSvelte.replace(/<button class="text-xs px-3 py-1 bg-ge-bg border border-ge-border rounded hover:bg-ge-border transition-colors" on:click=\{\(\) => \{\n\s*if \(\!slides\.length\) return;\n\s*const html = slides\[currentSlideIndex\]\.html;\n\s*const blob = new Blob\(\[html\], \{ type: 'text\/html' \}\);\n\s*const link = document\.createElement\('a'\);\n\s*link\.download = `slide_\$\{currentSlideIndex \+ 1\}\.html`;\n\s*link\.href = URL\.createObjectURL\(blob\);\n\s*link\.click\(\);\n\s*URL\.revokeObjectURL\(link\.href\);\n\s*\}\}>Export HTML<\/button>/g, exportHtmlBar);

// Add the editor text area overlay
const iframeArea = `
        <iframe
          bind:this={iframeElement}
          title="Slide Preview"
          srcdoc={iframeSrcDoc}
          class="w-full h-full bg-white"
          sandbox="allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox"
        ></iframe>
        {#if isEditingHtml}
        <div class="absolute inset-0 bg-ge-bg z-10 flex flex-col">
          <div class="p-2 bg-ge-card text-xs border-b border-ge-border flex justify-between items-center">
            <span>Raw HTML Editor</span>
            <button class="px-2 py-1 bg-ge-accent rounded text-ge-bg font-bold" on:click={() => {
                isEditingHtml = false;
                slides[currentSlideIndex].html = editorHtml;
                const combined = [editorHtml].join('')
                    .replace(/\\\\n/g, '\\n').replace(/\\\\"/g, '"');
                try {
                    const doc = iframeElement?.contentDocument;
                    if (doc && doc.body) {
                        doc.body.innerHTML = combined;
                    } else {
                        iframeSrcDoc = combined;
                    }
                } catch(e) {
                    iframeSrcDoc = combined;
                }
            }}>Apply & Close</button>
          </div>
          <textarea bind:value={editorHtml} class="w-full flex-grow p-4 bg-[#1e1e1e] text-[#d4d4d4] font-mono text-sm resize-none focus:outline-none" placeholder="Paste your HTML here..."></textarea>
        </div>
        {/if}
`;

appSvelte = appSvelte.replace(/<iframe\n\s*bind:this=\{iframeElement\}\n\s*title="Slide Preview"\n\s*srcdoc=\{iframeSrcDoc\}\n\s*class="w-full h-full bg-white"\n\s*sandbox="allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox"\n\s*><\/iframe>/g, iframeArea);

// Add taepdf fix
appSvelte = appSvelte.replace("const html = slides[currentSlideIndex].html;",
    `const html = slides[currentSlideIndex].html;
          // Ensure exact color printing
          const htmlWithPrint = html.replace("</style>", "\\n@media print { * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; } }\\n</style>");`);

appSvelte = appSvelte.replace("await pdf.download(html, 'A4', `slide_${currentSlideIndex + 1}.pdf`, undefined, { orientation: 'landscape' });",
    "await pdf.download(htmlWithPrint, 'A4', `slide_${currentSlideIndex + 1}.pdf`, 'fillable', { orientation: 'landscape' });");

fs.writeFileSync('frontend_svelte/src/App.svelte', appSvelte);

const styleBankFiles = fs.readdirSync('style_bank');
styleBankFiles.forEach(file => {
    let content = fs.readFileSync(`style_bank/${file}`, 'utf-8');
    let data = JSON.parse(content);
    if(data.print_css) {
        data.print_css = data.print_css.replace(/body\s*\{\s*background:\s*[^;]+;\s*color:\s*[^;]+;\s*\}/g, "");
        data.print_css = data.print_css.replace(/\.ge-card\s*\{[^}]+\}/g, "");
        data.print_css = data.print_css.replace(/\.dark-card\s*\{[^}]+\}/g, "");
        data.print_css = data.print_css.replace(/body\s*\{\s*font-size:\s*12pt;\s*\}/g, "");
        data.print_css = data.print_css.replace(/\.ge-accent\s*\{[^}]+\}/g, "");
    }
    fs.writeFileSync(`style_bank/${file}`, JSON.stringify(data, null, 2));
});

let indexHtml = fs.readFileSync('index.html', 'utf-8');
indexHtml = indexHtml.replace('<button onclick="window.print()" title="Print / PDF">PDF</button>', '');
fs.writeFileSync('index.html', indexHtml);
