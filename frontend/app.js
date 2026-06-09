        // ── State ──────────────────────────────────────────────────────────
        const historyDiv = document.getElementById('history');
        const promptBox = document.getElementById('prompt');
        const pageCountBox = document.getElementById('page-count');
        const slideLayoutBox = document.getElementById('slide-layout');
        const statusDiv = document.getElementById('status');
        const slideFrame = document.getElementById('slide-frame');
        const slideInfo = document.getElementById('slide-info');
        const genBtn = document.getElementById('gen-btn');
        const stopBtn = document.getElementById('stop-btn');
        const prevBtn = document.getElementById('prev-btn');
        const nextBtn = document.getElementById('next-btn');
        const slideCounter = document.getElementById('slide-counter');
        
        const backendURL = '/command';
        const uploadURL = '/upload';
        const stylesURL = '/styles';
        
        let currentSlides = [];
        let currentSlideIdx = 0;
        let currentController = null;
        let selectedFormat = 'slides';
        let selectedStyle = 'auto';
        let availableStyles = [];

        // ── Toast ──────────────────────────────────────────────────────────
        function showToast(msg, duration = 2000) {
            const t = document.getElementById('toast');
            t.textContent = msg;
            t.classList.add('show');
            setTimeout(() => t.classList.remove('show'), duration);
        }

        // ── Format selector ────────────────────────────────────────────────
        function selectFormat(el) {
            document.querySelectorAll('[data-format]').forEach(p => p.classList.remove('active'));
            el.classList.add('active');
            selectedFormat = el.dataset.format;
        }



        // ── Style selector ─────────────────────────────────────────────────
        async function loadStyles() {
            try {
                const resp = await fetch(stylesURL);
                availableStyles = await resp.json();
                renderStylePills();
            } catch (e) {
                console.warn('Could not load styles:', e);
            }
        }

        function renderStylePills() {
            const container = document.getElementById('style-selector');
            container.innerHTML = '';
            availableStyles.forEach((s, idx) => {
                const pill = document.createElement('span');
                pill.className = 'pill' + (idx === 0 ? ' active-style' : '');
                pill.dataset.style = s.id;
                pill.onclick = () => selectStyle(s.id);
                pill.textContent = s.name;
                container.appendChild(pill);
            });
        }

        function selectStyle(id) {
            selectedStyle = id;
            document.querySelectorAll('[data-style]').forEach(p => p.classList.remove('active-style'));
            const target = document.querySelector(`[data-style="${id}"]`);
            if (target) target.classList.add('active-style');
        }

        // ── Slide navigation ───────────────────────────────────────────────
        function updateSlideNav() {
            prevBtn.disabled = currentSlideIdx <= 0;
            nextBtn.disabled = currentSlideIdx >= currentSlides.length - 1;
            slideCounter.textContent = currentSlides.length > 0 
                ? `${currentSlideIdx + 1} / ${currentSlides.length}` 
                : 'No slides';
            slideInfo.textContent = currentSlides.length > 0 
                ? `Slide ${currentSlideIdx + 1} of ${currentSlides.length}` 
                : 'No slides';
        }

        function showSlide(idx) {
            if (idx >= 0 && idx < currentSlides.length) {
                currentSlideIdx = idx;
                slideFrame.srcdoc = currentSlides[idx].html;
                updateSlideNav();
            }
        }

        function prevSlide() { showSlide(currentSlideIdx - 1); }
        function nextSlide() { showSlide(currentSlideIdx + 1); }

        function addMessage(text, type) {
            const div = document.createElement('div');
            div.className = `msg ${type}`;
            div.textContent = text;
            historyDiv.appendChild(div);
            historyDiv.scrollTop = historyDiv.scrollHeight;
        }

        // ── Main generation ────────────────────────────────────────────────
        async function sendCommand() {
            if (genBtn.disabled) return;
            const text = promptBox.value.trim();
            if (!text) {
                statusDiv.textContent = 'Enter a prompt first!';
                return;
            }
            
            genBtn.disabled = true;
            stopBtn.disabled = false;
            
            addMessage(`[${selectedFormat} / ${selectedStyle}] ${text}`, 'user');
            promptBox.value = '';
            statusDiv.textContent = 'Generating...';
            
            const thinkingDiv = document.createElement('div');
            thinkingDiv.className = 'msg agent thinking';
            thinkingDiv.textContent = '[Thinking...]';
            historyDiv.appendChild(thinkingDiv);
            historyDiv.scrollTop = historyDiv.scrollHeight;

            currentController = new AbortController();
            let liveHtmlChunks = [];
            let thinkingBuffer = '';

            try {
                const response = await fetch(backendURL, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        message: text,
                        format: selectedFormat,
                        style: selectedStyle,
                        page_count: parseInt(pageCountBox.value) || 5,
                        layout: slideLayoutBox.value,
                    }),
                    signal: currentController.signal
                });

                if (!response.ok) throw new Error("Server error: " + response.status);
                
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';
                
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    
                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop();
                    
                    for (const line of lines) {
                        if (line.startsWith('data:')) {
                            const dataStr = line.substring(5).trim();
                            if (!dataStr || dataStr === '[DONE]') continue;
                            
                            try {
                                const data = JSON.parse(dataStr);
                                
                                if (data.type === 'thinking') {
                                    thinkingBuffer += data.text;
                                    if (thinkingBuffer.length > 20) {
                                        thinkingDiv.textContent += thinkingBuffer;
                                        historyDiv.scrollTop = historyDiv.scrollHeight;
                                        thinkingBuffer = '';
                                    }
                                }
                                
                                if (data.type === 'answer') {
                                    if (thinkingBuffer) {
                                        thinkingDiv.textContent += thinkingBuffer;
                                        historyDiv.scrollTop = historyDiv.scrollHeight;
                                        thinkingBuffer = '';
                                    }
                                    let answerDiv = historyDiv.querySelector('.msg.answer');
                                    if (!answerDiv) {
                                        answerDiv = document.createElement('div');
                                        answerDiv.className = 'msg agent answer';
                                        historyDiv.appendChild(answerDiv);
                                    }
                                    answerDiv.textContent += data.text;
                                    historyDiv.scrollTop = historyDiv.scrollHeight;
                                }
                                
                                if (data.type === 'slide_page') {
                                    if (thinkingBuffer) {
                                        thinkingDiv.textContent += thinkingBuffer;
                                        historyDiv.scrollTop = historyDiv.scrollHeight;
                                        thinkingBuffer = '';
                                    }
                                    liveHtmlChunks.push(data.html || '');
                                    const combined = liveHtmlChunks.join('')
                                        .replace(/\\n/g, '\n').replace(/\\"/g, '"');
                                    try {
                                        const doc = slideFrame.contentDocument;
                                        if (doc && doc.body && doc.body.innerHTML.length > 0) {
                                            const prevScroll = doc.documentElement.scrollTop || doc.body.scrollTop;
                                            doc.body.innerHTML = combined;
                                            doc.documentElement.scrollTop = doc.body.scrollTop = prevScroll;
                                        } else {
                                            slideFrame.srcdoc = combined;
                                        }
                                    } catch(e) {
                                        slideFrame.srcdoc = combined;
                                    }
                                    statusDiv.textContent = `Streaming... (${liveHtmlChunks.length} chunks)`;
                                }
                                
                                if (data.type === 'final_html') {
                                    if (thinkingBuffer) {
                                        thinkingDiv.textContent += thinkingBuffer;
                                        historyDiv.scrollTop = historyDiv.scrollHeight;
                                        thinkingBuffer = '';
                                    }
                                    const html = data.html;
                                    slideFrame.srcdoc = html;
                                    currentSlides.push({ html, title: text });
                                    currentSlideIdx = currentSlides.length - 1;
                                    updateSlideNav();
                                    statusDiv.textContent = 'Done!';
                                    thinkingDiv.textContent = `[Complete — ${selectedFormat} / ${selectedStyle}]`;
                                    thinkingDiv.className = 'msg agent';
                                    
                                    genBtn.disabled = false;
                                    stopBtn.disabled = true;
                                    currentController = null;
                                    return;
                                }
                                if (data.type === 'error') {
                                    if (thinkingBuffer) {
                                        thinkingDiv.textContent += thinkingBuffer;
                                        historyDiv.scrollTop = historyDiv.scrollHeight;
                                        thinkingBuffer = '';
                                    }
                                    thinkingDiv.textContent = 'Error: ' + data.text;
                                    thinkingDiv.className = 'msg agent';
                                    statusDiv.textContent = 'Error';
                                }
                            } catch (e) {}
                        }
                    }
                }
                
                statusDiv.textContent = 'Done';
            } catch (err) {
                if (err.name === 'AbortError') {
                    statusDiv.textContent = 'Stopped';
                    thinkingDiv.textContent = '[Stopped]';
                } else {
                    statusDiv.textContent = 'Error: ' + err.message;
                    thinkingDiv.textContent = 'Error: ' + err.message;
                    addMessage('Connection error — is the server running on port 2828?', 'agent');
                }
            } finally {
                genBtn.disabled = false;
                stopBtn.disabled = true;
                currentController = null;
            }
        }

        function stopRequest() {
            if (currentController) {
                currentController.abort();
                statusDiv.textContent = 'Stopping...';
            }
        }

        // ── Upload ─────────────────────────────────────────────────────────
        async function uploadFile() {
            const fileInput = document.getElementById('file-input');
            if (!fileInput.files.length) return;
            
            const formData = new FormData();
            formData.append('file', fileInput.files[0]);
            
            statusDiv.textContent = 'Uploading...';
            try {
                const response = await fetch(uploadURL, { method: 'POST', body: formData });
                const data = await response.json();
                statusDiv.textContent = data.id ? 'Uploaded: ' + data.id : 'Done';
                addMessage('File uploaded: ' + fileInput.files[0].name, 'agent');
            } catch (e) {
                statusDiv.textContent = 'Upload failed';
            }
            fileInput.value = '';
        }

        // ── Clear ──────────────────────────────────────────────────────────
        function clearHistory() {
            if (confirm('Clear all?')) {
                currentSlides = [];
                currentSlideIdx = 0;
                slideFrame.srcdoc = '<html><body style="display:flex;align-items:center;justify-content:center;height:100vh;background:#f5f5f5;color:#999;"><h3>Slide Preview</h3></body></html>';
                historyDiv.innerHTML = '<div class="msg agent">Cleared</div>';
                updateSlideNav();
                statusDiv.textContent = 'Ready';
            }
        }

        // ── Export ─────────────────────────────────────────────────────────
        async function exportPNG() {
            if (!currentSlides.length) return;
            try {
                statusDiv.textContent = 'Capturing...';
                const iframeDoc = slideFrame.contentDocument || slideFrame.contentWindow.document;
                const canvas = await html2canvas(iframeDoc.body, {
                    scale: 2,
                    useCORS: true,
                    backgroundColor: '#ffffff',
                    width: slideFrame.clientWidth,
                    height: slideFrame.clientHeight,
                });
                const link = document.createElement('a');
                link.download = `slide_${currentSlideIdx + 1}.png`;
                link.href = canvas.toDataURL('image/png');
                link.click();
                statusDiv.textContent = 'PNG exported!';
            } catch (e) {
                statusDiv.textContent = 'Export failed: ' + e.message;
            }
        }

        function exportHTML() {
            if (!currentSlides.length) return;
            const html = currentSlides[currentSlideIdx].html;
            const blob = new Blob([html], { type: 'text/html' });
            const link = document.createElement('a');
            link.download = `slide_${currentSlideIdx + 1}.html`;
            link.href = URL.createObjectURL(blob);
            link.click();
            URL.revokeObjectURL(link.href);
        }

        function openFullscreen() {
            if (!currentSlides.length) return;
            const html = currentSlides[currentSlideIdx].html;
            const w = window.open('', '_blank');
            w.document.write(html);
            w.document.close();
        }

        // ── HTML Editor ────────────────────────────────────────────────────
        let editorVisible = false;

        function toggleEditor() {
            editorVisible = !editorVisible;
            const panel = document.getElementById('html-editor-panel');
            const btn = document.getElementById('edit-toggle-btn');
            if (editorVisible) {
                panel.classList.remove('hidden');
                btn.classList.add('active');
                btn.textContent = 'Close Editor';
                if (currentSlides.length > 0) {
                    document.getElementById('html-editor').value = currentSlides[currentSlideIdx].html;
                }
            } else {
                panel.classList.add('hidden');
                btn.classList.remove('active');
                btn.textContent = 'Edit HTML';
            }
        }

        function applyHTML() {
            const editor = document.getElementById('html-editor');
            const html = editor.value;
            if (!html.trim()) return;
            slideFrame.srcdoc = html;
            if (currentSlides.length > 0) {
                currentSlides[currentSlideIdx].html = html;
            }
            showToast('Preview updated');
        }

        function formatHTML() {
            const editor = document.getElementById('html-editor');
            let html = editor.value;
            let formatted = '';
            let indent = 0;
            const tab = '  ';
            html.split(/>\s*</).forEach(function(node) {
                if (node.match(/^\/\w/)) indent--;
                formatted += new Array(indent + 1).join(tab) + '<' + node + '>\n';
                if (node.match(/^<?\w[^>]*[^\/]$/)) indent++;
            });
            editor.value = formatted.substring(1, formatted.length - 2);
        }

        // ── Keyboard shortcuts ─────────────────────────────────────────────
        promptBox.addEventListener('keydown', e => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendCommand();
            }
        });

        document.addEventListener('keydown', e => {
            if (e.ctrlKey || e.metaKey) {
                if (e.key === 's') {
                    e.preventDefault();
                    exportPNG();
                }
                if (e.key === 'Enter') {
                    e.preventDefault();
                    if (!genBtn.disabled) sendCommand();
                }
            }
            if (e.key === 'ArrowLeft' && !e.target.closest('textarea, input')) prevSlide();
            if (e.key === 'ArrowRight' && !e.target.closest('textarea, input')) nextSlide();
        });

        // ── Saved Slides Browser ────────────────────────────────────────────
        function switchTab(tab) {
            document.querySelectorAll('.sidebar-tab').forEach(t => t.classList.remove('active'));
            document.querySelector(`[onclick="switchTab('${tab}')"]`).classList.add('active');
            if (tab === 'saved') {
                document.getElementById('history').classList.add('hidden');
                document.getElementById('saved-panel').classList.remove('hidden');
                loadSavedSlides();
            } else {
                document.getElementById('history').classList.remove('hidden');
                document.getElementById('saved-panel').classList.add('hidden');
            }
        }

        async function loadSavedSlides() {
            const list = document.getElementById('saved-list');
            try {
                const resp = await fetch('/saved');
                const slides = await resp.json();
                if (!slides.length) {
                    list.innerHTML = '<div class="saved-empty">No saved slides yet</div>';
                    return;
                }
                list.innerHTML = slides.map(s => `
                    <div class="saved-item" onclick="loadSavedSlide('${s.filename}', '${s.title.replace(/'/g, "\\'")}')">
                        <div class="saved-item-title">${s.title}</div>
                        <div class="saved-item-date">${s.date} — ${(s.size / 1024).toFixed(1)} KB</div>
                    </div>
                `).join('');
            } catch (e) {
                list.innerHTML = '<div class="saved-empty">Could not load saved slides</div>';
            }
        }

        function loadSavedSlide(filename, title) {
            fetch('/saved/' + filename)
                .then(r => r.text())
                .then(html => {
                    slideFrame.srcdoc = html;
                    currentSlides = [{ html, title: title || filename }];
                    currentSlideIdx = 0;
                    updateSlideNav();
                    statusDiv.textContent = 'Loaded: ' + (title || filename);
                    switchTab('chat');
                    addMessage('[Loaded] ' + (title || filename), 'agent');
                })
                .catch(() => {
                    statusDiv.textContent = 'Failed to load slide';
                });
        }

        // ── Init ───────────────────────────────────────────────────────────
        fetch('/version')
            .then(r => r.json())
            .then(data => {
                if (data.version && data.git_commit) {
                    document.getElementById('version-info').textContent = 
                        `v${data.version} (${data.git_commit})`;
                }
            })
            .catch(() => {});
        
        loadStyles();

        slideFrame.srcdoc = '<html><body style="display:flex;align-items:center;justify-content:center;height:100vh;background:#f5f5f5;color:#999;font-family:sans-serif;"><div style="text-align:center"><h3>Slide Preview</h3><p style="margin-top:8px;font-size:13px;">Pick format + style, describe what you want, hit Generate</p></div></body></html>';
