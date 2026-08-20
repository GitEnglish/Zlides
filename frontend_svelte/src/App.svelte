<script lang="ts">
  import { onMount, tick } from 'svelte';
  import SvelteMarkdown from '@humanspeak/svelte-markdown';
  import { markedMermaid, MermaidRenderer } from '@humanspeak/svelte-markdown/extensions';
  import type { StreamingChunk, RendererComponent, Renderers } from '@humanspeak/svelte-markdown';

  interface MermaidRenderers extends Renderers {
      mermaid: RendererComponent;
  }

  const renderers: Partial<MermaidRenderers> = {
      mermaid: MermaidRenderer
  };

  let cost = 0.00;
  let isGenerating = false;
  let isBatchMode = false;
  let isUploading = false;
  let isEditingHtml = false;
  let isExportingPdf = false;
  let editorHtml = '';
  let status = "Ready";

  let slides: any[] = [];
  let currentSlideIndex = 0;
  // Included a mock RR button to prove the concept works when dropped in
  let iframeSrcDoc = "<html><body style='display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;background:#262424;color:#9e9e9e;font-family:sans-serif;'><h3>Zlides V2 Preview</h3><p>Example RR Student Exercise below:</p><br><button id='regenerate' data-prompt='Give me a new math problem' style='padding:8px 16px;background:#ff6600;color:#fff;border:none;border-radius:4px;cursor:pointer;'>Regenerate Exercise</button><script>document.querySelectorAll('button[id=\"regenerate\"]').forEach(b=>b.addEventListener('click',function(){window.parent.postMessage({type:'regenerate',prompt:this.getAttribute('data-prompt')},'*');this.innerText='Regenerating...';}));<\/script></body></html>";

  let promptText = "";
  let files: FileList | null = null;
  let extractedMarkdown = "";

  let availableFormats: any[] = [];
  let availableLayouts: any[] = [];
  let savedSlides: any[] = [];
  let isSavedModalOpen = false;
  let isLoadingSaved = false;
  let savedSearchQuery = "";

  onMount(async () => {
    // Warmup taepdf WASM engine in the background
    try {
      const { default: pdf } = await import('taepdf');
      pdf.warmup().catch(err => console.warn("taepdf warmup background error:", err));
    } catch (e) {
      console.warn("Could not warmup taepdf:", e);
    }
    // Load styles from the backend
    try {
      const resp = await fetch("/styles");
      availableStyles = await resp.json();
    } catch (e) {
      console.warn("Could not load styles:", e);
    }

    // Load formats from the backend
    try {
      const resp = await fetch("/formats");
      availableFormats = await resp.json();
    } catch (e) {
      console.warn("Could not load formats:", e);
    }

    // Load agnostic layouts from the backend
    try {
      const resp = await fetch("/layouts");
      availableLayouts = await resp.json();
    } catch (e) {
      console.warn("Could not load layouts:", e);
    }

    // Load saved slides
    loadSavedSlides();

    // Listen for RR format regeneration requests from the iframe
    window.addEventListener('message', (event) => {
      if (event.data && event.data.type === 'regenerate') {
        status = `RR Event: Triggering regeneration with prompt: "${event.data.prompt}"`;
        // We'd pass this to the backend with the ongoing conversation_id to patch the slide
        setTimeout(() => {
          status = "Ready";
          // We'd postMessage back to the iframe to swap the HTML here
        }, 2000);
      }
    });
  });

  async function loadSavedSlides() {
    isLoadingSaved = true;
    try {
      const resp = await fetch("/saved");
      savedSlides = await resp.json();
    } catch (e) {
      console.warn("Could not load saved slides:", e);
    } finally {
      isLoadingSaved = false;
    }
  }

  async function selectSavedSlide(slide: any) {
    status = `Loading ${slide.title || slide.filename}...`;
    try {
      const resp = await fetch('/saved/' + encodeURIComponent(slide.filename));
      const html = await resp.text();
      slides = [{ html, title: slide.title || slide.filename }];
      currentSlideIndex = 0;
      iframeSrcDoc = html;
      isSavedModalOpen = false;
      status = `Loaded: ${slide.title || slide.filename}`;
      addMessage(`[Loaded Saved Slide] **${slide.title || slide.filename}** (${slide.date})`, 'agent');
    } catch (err: any) {
      status = `Failed to load slide: ${err.message}`;
    }
  }

  $: filteredSavedSlides = savedSlides.filter(s => {
    if (!savedSearchQuery.trim()) return true;
    const q = savedSearchQuery.toLowerCase();
    return (s.title && s.title.toLowerCase().includes(q)) ||
           (s.filename && s.filename.toLowerCase().includes(q)) ||
           (s.date && s.date.toLowerCase().includes(q));
  });

  $: formatList = availableFormats.length > 0 ? availableFormats : [
    { id: "slides", name: "Slides" },
    { id: "guide", name: "Guide" },
    { id: "lac", name: "LAC v5" },
    { id: "poster", name: "Poster" },
    { id: "worksheet", name: "Worksheet" },
    { id: "report", name: "Report" },
    { id: "rr", name: "RegenResource" }
  ];

  async function updateCost() {
    if (!promptText.trim() && !files) {
      cost = 0;
      return;
    }
    try {
      const res = await fetch("/estimate-cost", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: promptText + extractedMarkdown,
          files_attached: files ? files.length : 0
        })
      });
      const data = await res.json();
      cost = data.cost_usd;
    } catch (e) {
      console.error(e);
    }
  }

  $: promptText, updateCost();
  $: isBatchMode = promptText.toLowerCase().includes("batch") || promptText.includes("\n\n");

  async function handleFileSelect(e: Event) {
    const target = e.target as HTMLInputElement;
    if (target.files && target.files.length > 0) {
      files = target.files;
      isUploading = true;
      status = `Ingesting ${files[0].name} via File Parser API...`;

      const formData = new FormData();
      formData.append("file", files[0]);

      const isStyle = promptText.toLowerCase().includes("style") || files[0].type.includes("image");
      formData.append("type", isStyle ? "style" : "file");

      try {
        const res = await fetch("/upload", { method: "POST", body: formData });
        const data = await res.json();

        extractedMarkdown = data.parsed_markdown || "";

        if (data.style_extracted) {
          status = `Reverse engineered style "${data.style_extracted.name}" saved!`;
        } else {
          status = "File parsed into Markdown. Ready to generate.";
        }
        updateCost();
      } catch (err) {
        status = "Upload / Parsing failed.";
      }
      isUploading = false;
    }
  }

  let currentController: AbortController | null = null;
  let liveHtmlChunks: string[] = [];
  let iframeElement: HTMLIFrameElement | null = null;
  let thinkingBuffer = '';

  // We'll define these fully in Step 3, but provide stubs to make TS happy
  let chatMessages: any[] = [{ role: "agent", text: "Ready! Pick a format + style, describe what you want." }];
  let selectedFormat = "slides";
  let selectedStyle = "auto";
  let pageCount: number | null = null;
  let slideLayout = "";
  let availableStyles: any[] = [];

  function renderLiveHtmlChunks() {
    const combined = liveHtmlChunks.join('')
        .replace(/\\n/g, '\n').replace(/\\"/g, '"');
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
    status = `Streaming... (${liveHtmlChunks.length} chunks)`;
  }

  function addMessage(text: string, role: string) {
    chatMessages = [...chatMessages, { role, text }];
    // Ensure scrolling happens after DOM update
    setTimeout(() => {
      const historyDiv = document.getElementById("chat-history");
      if (historyDiv) {
        historyDiv.scrollTop = historyDiv.scrollHeight;
      }
    }, 10);
  }

  function stopRequest() {
    if (currentController) {
      currentController.abort();
      status = 'Stopping...';
    }
  }

  async function generate() {
    if (!promptText.trim() && !extractedMarkdown) return;
    isGenerating = true;

    if (isBatchMode) {
      status = "Batch Scheduling... (Semaphore limited)";
      const prompts = promptText.split(/\n\n+/).filter(p => p.trim());
      try {
        const res = await fetch("/batch", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ prompts })
        });
        const data = await res.json();
        status = `Batch completed! ${data.results.length} processed.`;
      } catch (e) {
        status = "Batch failed.";
      }
      isGenerating = false;
      return;
    }

    const textToSend = promptText;
    promptText = "";
    status = "Generating...";
    addMessage(`[${selectedFormat} / ${selectedStyle}] ${textToSend}`, 'user');
    addMessage('[Thinking...]', 'thinking'); // placeholder

    currentController = new AbortController();
    liveHtmlChunks = [];
    thinkingBuffer = '';

    try {
      const response = await fetch('/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: textToSend + (extractedMarkdown ? "\n\n" + extractedMarkdown : ""),
          format: selectedFormat,
          style: selectedStyle,
          page_count: pageCount ? Number(pageCount) : undefined,
          layout: slideLayout,
        }),
        signal: currentController.signal
      });

      if (!response.ok) throw new Error("Server error: " + response.status);

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data:')) {
              const dataStr = line.substring(5).trim();
              if (!dataStr || dataStr === '[DONE]') continue;

              try {
                const data = JSON.parse(dataStr);

                if (data.type === 'thinking') {
                  thinkingBuffer += data.text;
                  if (thinkingBuffer.length > 20) {
                    // Update the last thinking message
                    const lastMsg = chatMessages[chatMessages.length - 1];
                    if (lastMsg && lastMsg.role === 'thinking') {
                      lastMsg.text = lastMsg.text === '[Thinking...]' ? thinkingBuffer : lastMsg.text + thinkingBuffer;
                      chatMessages = [...chatMessages];
                    }
                    thinkingBuffer = '';
                  }
                }

                if (data.type === 'answer') {
                  if (thinkingBuffer) {
                    const lastMsg = chatMessages[chatMessages.length - 1];
                    if (lastMsg && lastMsg.role === 'thinking') {
                      lastMsg.text = lastMsg.text === '[Thinking...]' ? thinkingBuffer : lastMsg.text + thinkingBuffer;
                    }
                    thinkingBuffer = '';
                  }

                  const lastMsg = chatMessages[chatMessages.length - 1];
                  if (lastMsg && lastMsg.role === 'agent') {
                    lastMsg.text += data.text;
                    chatMessages = [...chatMessages];
                  } else {
                    addMessage(data.text, 'agent');
                  }
                }

                if (data.type === 'slide_page') {
                  if (thinkingBuffer) {
                    const lastMsg = chatMessages[chatMessages.length - 1];
                    if (lastMsg && lastMsg.role === 'thinking') {
                      lastMsg.text = lastMsg.text === '[Thinking...]' ? thinkingBuffer : lastMsg.text + thinkingBuffer;
                    }
                    thinkingBuffer = '';
                  }
                  liveHtmlChunks.push(data.html || '');
                  renderLiveHtmlChunks();
                }

                if (data.type === 'slide_remove') {
                  console.log("Removing slides at positions:", data.positions);
                }

                if (data.type === 'slide_replace') {
                  if (thinkingBuffer) {
                    const lastMsg = chatMessages[chatMessages.length - 1];
                    if (lastMsg && lastMsg.role === 'thinking') {
                      lastMsg.text = lastMsg.text === '[Thinking...]' ? thinkingBuffer : lastMsg.text + thinkingBuffer;
                    }
                    thinkingBuffer = '';
                  }
                  liveHtmlChunks.push(data.html || '');
                  renderLiveHtmlChunks();
                }

                if (data.type === 'slide_navigate') {
                  if (data.position && data.position.length > 0) {
                    currentSlideIndex = Math.max(0, data.position[0] - 1);
                  }
                }

                if (data.type === 'final_html') {
                  if (thinkingBuffer) {
                    const lastMsg = chatMessages[chatMessages.length - 1];
                    if (lastMsg && lastMsg.role === 'thinking') {
                      lastMsg.text = lastMsg.text === '[Thinking...]' ? thinkingBuffer : lastMsg.text + thinkingBuffer;
                    }
                    thinkingBuffer = '';
                  }

                  // Convert thinking message to agent message if it was just thinking
                  const lastMsg = chatMessages[chatMessages.length - 1];
                  if (lastMsg && lastMsg.role === 'thinking') {
                    lastMsg.text = `[Complete — ${selectedFormat} / ${selectedStyle}]`;
                    lastMsg.role = 'agent';
                    chatMessages = [...chatMessages];
                  }

                  const html = data.html;
                  iframeSrcDoc = html;
                  slides = [...slides, { html, title: textToSend }];
                  currentSlideIndex = slides.length - 1;
                  status = 'Done!';

                  isGenerating = false;
                  currentController = null;
                  return;
                }

                if (data.type === 'error') {
                  if (thinkingBuffer) {
                    const lastMsg = chatMessages[chatMessages.length - 1];
                    if (lastMsg && lastMsg.role === 'thinking') {
                      lastMsg.text = lastMsg.text === '[Thinking...]' ? thinkingBuffer : lastMsg.text + thinkingBuffer;
                    }
                    thinkingBuffer = '';
                  }

                  const lastMsg = chatMessages[chatMessages.length - 1];
                  if (lastMsg && lastMsg.role === 'thinking') {
                    lastMsg.text = 'Error: ' + data.text;
                    lastMsg.role = 'agent';
                    chatMessages = [...chatMessages];
                  } else {
                     addMessage('Error: ' + data.text, 'agent');
                  }
                  status = 'Error';
                }
              } catch (e) {}
            }
          }
        }
      }
      status = 'Done';
    } catch (err: any) {
      if (err.name === 'AbortError') {
        status = 'Stopped';
        const lastMsg = chatMessages[chatMessages.length - 1];
        if (lastMsg && lastMsg.role === 'thinking') {
          lastMsg.text = '[Stopped]';
          lastMsg.role = 'agent';
          chatMessages = [...chatMessages];
        }
      } else {
        status = 'Error: ' + err.message;
        addMessage('Connection error — is the server running on port 2828?', 'agent');
      }
    } finally {
      isGenerating = false;
      currentController = null;
    }
  }
</script>

<main class="min-h-screen bg-ge-bg text-ge-text flex flex-col md:flex-row h-screen overflow-hidden">

  <div class="w-full md:w-1/3 p-6 flex flex-col gap-4 bg-ge-card border-r border-ge-border shadow-2xl z-10 flex-shrink-0 relative overflow-hidden">
    <div class="space-y-2 flex-shrink-0">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <h1 class="text-3xl font-bold tracking-tight text-ge-accent font-raleway">Zlides V2</h1>
          {#if isBatchMode}
            <span class="bg-ge-bg text-xs px-2 py-1 rounded border border-ge-border text-ge-accent animate-pulse">Batch Mode</span>
          {:else}
            <span class="bg-ge-bg text-xs px-2 py-1 rounded border border-ge-border text-ge-text-muted">Mongoose Fast</span>
          {/if}
        </div>
        <button
          class="text-xs px-3 py-1.5 bg-ge-bg border border-ge-border hover:border-ge-accent rounded-lg text-ge-accent font-medium transition-colors flex items-center gap-1.5 shadow-sm"
          on:click={() => { isSavedModalOpen = true; loadSavedSlides(); }}
          title="Browse and select saved slides and past classes"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"/></svg>
          Past Classes ({savedSlides.length})
        </button>
      </div>
      <p class="text-ge-text-muted text-sm">Drop vibes. Get slides. The smart parser extracts layout + style from uploaded files.</p>
    </div>

    <!-- UI Controls -->
    <div class="flex flex-col gap-2 flex-shrink-0 text-sm">
      <div class="flex gap-2 flex-wrap">
        {#each formatList as fmt}
          <button
            class="px-3 py-1 rounded-full border border-ge-border transition-colors text-xs {selectedFormat === fmt.id ? 'bg-ge-accent text-ge-bg font-bold border-ge-accent' : 'bg-ge-bg text-ge-text hover:bg-ge-border'}"
            title={fmt.description || fmt.name}
            on:click={() => selectedFormat = fmt.id}
          >
            {fmt.name || fmt.id}
          </button>
        {/each}
      </div>

      <div class="flex gap-2 flex-wrap mt-2">
        {#each availableStyles as style}
          <button
            class="px-3 py-1 rounded-full border border-ge-border transition-colors text-xs {selectedStyle === style.id ? 'bg-ge-accent text-ge-bg font-bold border-ge-accent' : 'bg-ge-bg text-ge-text hover:bg-ge-border'}"
            on:click={() => selectedStyle = style.id}
          >
            {style.name}
          </button>
        {/each}
      </div>

      <div class="flex gap-2 mt-2">
        <input type="number" bind:value={pageCount} min="1" max="20" placeholder="Pages: Auto" class="bg-ge-bg border border-ge-border rounded px-2 py-1 w-24 text-ge-text placeholder:text-ge-text-muted/60 outline-none text-xs" title="Page Count (Leave blank for automatic page count)">
        <select bind:value={slideLayout} class="bg-ge-bg border border-ge-border rounded px-2 py-1 text-ge-text flex-grow outline-none text-xs" title="Agnostic Layout Matrix">
          <option value="">Layout: Auto</option>
          {#each availableLayouts as l}
            <option value={l.id}>{l.name} ({l.id})</option>
          {/each}
        </select>
      </div>
    </div>

    <!-- Chat History -->
    <div id="chat-history" class="flex-grow overflow-y-auto flex flex-col gap-2 p-2 bg-ge-bg rounded-lg border border-ge-border relative neumorphic-inset text-sm">
      {#each chatMessages as msg}
        <div class="p-2 rounded max-w-[90%] whitespace-pre-wrap {msg.role === 'user' ? 'bg-ge-card text-ge-text ml-auto border border-ge-border' : 'bg-transparent text-ge-text-muted mr-auto'}">
          {#if msg.role !== 'user'}
            <div class="text-xs font-bold mb-1 {msg.role === 'thinking' ? 'text-ge-accent/70' : 'text-ge-accent'}">{msg.role === 'thinking' ? 'Thinking...' : 'Z.AI Agent'}</div>
          {/if}
          {#if msg.role === 'agent' || msg.role === 'thinking'}
            <div class="prose prose-invert prose-sm max-w-none">
              <SvelteMarkdown source={msg.text} extensions={[markedMermaid()]} {renderers} />
            </div>
          {:else}
            {msg.text}
          {/if}
        </div>
      {/each}
    </div>

    <div class="flex flex-col gap-2 flex-shrink-0">
      <div class="flex flex-col bg-ge-bg rounded-lg p-2 border border-ge-border relative neumorphic-inset h-24">
        <textarea
          bind:value={promptText}
          on:keydown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); generate(); } }}
          placeholder="Describe your vibe... (e.g. 'Turn this uploaded PDF into slides.')"
          class="w-full h-full bg-transparent border-none outline-none resize-none p-1 text-ge-text placeholder:text-ge-text-muted/50 text-sm"
        ></textarea>

        <div class="absolute bottom-2 left-2 right-2 flex justify-between items-center bg-ge-bg/80 backdrop-blur rounded p-1">
           <label class="cursor-pointer text-xs flex items-center gap-1 bg-ge-card px-3 py-1.5 rounded border border-ge-border hover:bg-ge-border transition-colors disabled:opacity-50" class:opacity-50={isUploading}>
             {#if isUploading}
               <span class="animate-spin h-3 w-3 border-2 border-ge-accent border-t-transparent rounded-full"></span>
             {:else}
               <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/></svg>
             {/if}
             Ingest Document / Style
             <input type="file" class="hidden" on:change={handleFileSelect} accept=".pdf,.png,.jpg,.jpeg,.doc,.docx" disabled={isUploading} />
           </label>

           {#if files}
             <span class="text-xs text-ge-accent truncate max-w-[120px]" title={files[0].name}>{files[0].name}</span>
           {/if}
        </div>
      </div>

      <div class="p-3 bg-ge-bg rounded-lg font-mono text-xs border border-ge-border flex justify-between items-center">
        <span class="text-ge-text-muted flex items-center gap-2">
          <span class="relative flex h-2 w-2">
            {#if isGenerating || isUploading}
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-ge-accent opacity-75"></span>
            <span class="relative inline-flex rounded-full h-2 w-2 bg-ge-accent"></span>
            {:else}
            <span class="relative inline-flex rounded-full h-2 w-2 bg-ge-success"></span>
            {/if}
          </span>
          Estimated Cost
        </span>
        <span class="text-ge-success font-bold text-sm">${cost.toFixed(3)} USD</span>
      </div>

      <div class="flex gap-2">
        {#if isGenerating && !isBatchMode}
          <button
            on:click={stopRequest}
            class="flex-grow bg-ge-danger text-ge-bg font-bold py-3 rounded-lg hover:bg-ge-danger/80 transition-colors shadow-lg">
            Stop
          </button>
        {:else}
          <button
            on:click={generate}
            disabled={isGenerating || isUploading}
            class="flex-grow bg-ge-accent text-ge-bg font-bold py-3 rounded-lg hover:bg-ge-accent-hover transition-colors shadow-lg hover:shadow-ge-accent/20 disabled:opacity-50 disabled:cursor-not-allowed">
            {isGenerating ? (isBatchMode ? 'Batching...' : 'Generating...') : (isBatchMode ? 'Schedule Batch' : 'Generate')}
          </button>
        {/if}
      </div>
      <div class="text-center text-xs text-ge-text-muted font-mono h-4 truncate">{status}</div>
    </div>
  </div>

  <div class="flex-grow bg-ge-bg relative flex flex-col">
    <div class="h-12 border-b border-ge-border flex justify-between items-center px-4 bg-ge-card/50">
      <div class="flex items-center gap-3">
        <div class="text-sm font-raleway font-bold">Preview Stage (RR Enabled)</div>
        <button
          class="text-xs px-2.5 py-1 bg-ge-bg border border-ge-border rounded hover:bg-ge-border text-ge-accent transition-colors flex items-center gap-1.5"
          on:click={() => { isSavedModalOpen = true; loadSavedSlides(); }}
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"/></svg>
          Past Classes ({savedSlides.length})
        </button>
      </div>
      <div class="flex gap-2">
        <button
          disabled={isExportingPdf || (!slides.length && !editorHtml && !iframeSrcDoc)}
          class="text-xs px-3 py-1 bg-ge-bg border border-ge-border rounded hover:bg-ge-border transition-colors disabled:opacity-50"
          on:click={async () => {
            const html = isEditingHtml && editorHtml ? editorHtml : (slides.length ? slides[currentSlideIndex].html : editorHtml || iframeSrcDoc);
            if (!html || isExportingPdf) return;
            isExportingPdf = true;
            status = "Generating PDF...";
            try {
              const { default: pdf } = await import('taepdf');
              await pdf.warmup();

              // 1. Strip any legacy @media print blocks that force white backgrounds
              let exportHtml = html.replace(/@media\s+print\s*\{[\s\S]*?\}\s*\}/gi, '');

              // 2. Resolve SVGs so stroke/fill/dimensions are explicit for isolated rendering
              exportHtml = exportHtml.replace(/<svg\b([^>]*)>/gi, (match, attrs) => {
                let updated = attrs;
                if (!updated.includes('stroke=')) updated += ' stroke="currentColor"';
                if (!updated.includes('fill=')) updated += ' fill="none"';
                if (!updated.includes('stroke-width=')) updated += ' stroke-width="2"';
                if (!updated.includes('width=')) updated += ' width="32"';
                if (!updated.includes('height=')) updated += ' height="32"';
                return `<svg${updated}>`;
              });

              // 3. Detect orientation (worksheets, reports, guides, posters, and LAC catalogs are portrait)
              const isPortrait = selectedFormat === 'worksheet' || selectedFormat === 'report' || selectedFormat === 'guide' || selectedFormat === 'poster' || selectedFormat === 'lac' || exportHtml.includes('Lesson Asset Catalog') || exportHtml.includes('Vocabulary') || exportHtml.includes('Action Items');
              const orientation = isPortrait ? 'portrait' : 'landscape';
              const pageWidthPt = isPortrait ? '595.28pt' : '841.89pt';

              // 4. Chunk multi-card grid containers into individual break-protected grid rows
              try {
                const parser = new DOMParser();
                const doc = parser.parseFromString(exportHtml, 'text/html');
                const gridContainers = doc.querySelectorAll('.grid-2, .grid-3, .grid-4, .row-2');
                gridContainers.forEach(container => {
                  const is3Col = container.classList.contains('grid-3');
                  const is4Col = container.classList.contains('grid-4');
                  const cols = is4Col ? 4 : (is3Col ? 3 : 2);
                  const children = Array.from(container.children);
                  if (children.length <= cols) return;
                  
                  const parent = container.parentNode;
                  if (!parent) return;
                  
                  for (let i = 0; i < children.length; i += cols) {
                    const row = doc.createElement('div');
                    row.className = `grid-row-${cols}`;
                    row.style.cssText = `display: grid; grid-template-columns: repeat(${cols}, 1fr); gap: 14px; margin-bottom: 14px; break-inside: avoid !important; page-break-inside: avoid !important;`;
                    const chunk = children.slice(i, i + cols);
                    chunk.forEach(child => row.appendChild(child));
                    parent.insertBefore(row, container);
                  }
                  parent.removeChild(container);
                });
                exportHtml = doc.documentElement.outerHTML;
              } catch (e) {
                console.warn("DOMParser grid chunking failed, falling back:", e);
              }

              // 5. Inject font-face rules, exact A4 print dimensions, and card break protection
              const baseEnhancementsCss = `
                @font-face{font-family:'Inter';src:url('/fonts/inter.woff2') format('woff2');font-weight:100 900;font-style:normal;}
                @font-face{font-family:'Roboto';src:url('/fonts/roboto.woff2') format('woff2');font-weight:100 900;font-style:normal;}
                @font-face{font-family:'Outfit';src:url('/fonts/outfit.woff2') format('woff2');font-weight:100 900;font-style:normal;}
                @font-face{font-family:'Raleway';src:url('/fonts/raleway.woff2') format('woff2');font-weight:100 900;font-style:normal;}
                
                html, body {
                  width: ${pageWidthPt} !important;
                  margin: 0 auto !important;
                  padding: 0 !important;
                  background: #0f1112 !important;
                  -webkit-print-color-adjust: exact !important;
                  print-color-adjust: exact !important;
                }
                
                .container, main, .page, section, .section {
                  display: block !important;
                }

                .container, main, .page {
                  width: 100% !important;
                  min-height: 100% !important;
                  box-sizing: border-box !important;
                  padding: 28pt 36pt !important;
                  background: inherit !important;
                  color: #e5e7eb !important;
                }

                section, .section {
                  margin-bottom: 24pt !important;
                }

                .grid-2, .grid-3, .grid-4, .row-2, [class^="grid-row-"] {
                  display: grid !important;
                  break-inside: avoid !important;
                  page-break-inside: avoid !important;
                }

                .card, .summary-box, .section-head, .header-row, .stats-row, .exercise, tr {
                  break-inside: avoid !important;
                  page-break-inside: avoid !important;
                  box-sizing: border-box !important;
                }

                input, textarea, select {
                  font-family: 'Roboto', 'Inter', sans-serif !important;
                  box-sizing: border-box !important;
                }
              `;

              if (exportHtml.includes('</head>')) {
                exportHtml = exportHtml.replace('</head>', `<style>\n${baseEnhancementsCss}\n</style>\n</head>`);
              } else if (exportHtml.includes('<style>')) {
                exportHtml = exportHtml.replace('</style>', `\n${baseEnhancementsCss}\n</style>`);
              } else {
                exportHtml = `<style>\n${baseEnhancementsCss}\n</style>\n` + exportHtml;
              }

              await pdf.download(exportHtml, 'A4', `slide_${currentSlideIndex + 1}.pdf`, 'fillable', { orientation });
              status = "Ready";
            } catch (e: any) {
              console.error("PDF generation failed:", e);
              status = "PDF generation failed: " + (e?.message || String(e));
            } finally {
              isExportingPdf = false;
            }
        }}>{isExportingPdf ? 'Exporting...' : 'Export PDF'}</button>

        <button class="text-xs px-3 py-1 bg-ge-bg border border-ge-border rounded hover:bg-ge-border transition-colors" on:click={() => {
          if (!slides.length) {
            slides = [{ html: editorHtml || '<html><body><div class="p-8"><h1>Paste your HTML here</h1></div></body></html>' }];
            currentSlideIndex = 0;
          }
          isEditingHtml = !isEditingHtml;
          if (isEditingHtml) {
            editorHtml = slides[currentSlideIndex]?.html || editorHtml;
          } else {
            if (editorHtml) {
              slides[currentSlideIndex] = { html: editorHtml };
              slides = [...slides];
              iframeSrcDoc = editorHtml;
            }
          }
        }}>{isEditingHtml ? 'Apply HTML' : 'Edit / Paste HTML'}</button>
        <button class="text-xs px-3 py-1 bg-ge-bg border border-ge-border rounded hover:bg-ge-border transition-colors" on:click={() => {
          if (!slides.length) return;
          const html = slides[currentSlideIndex].html;
          const blob = new Blob([html], { type: 'text/html' });
          const link = document.createElement('a');
          link.download = `slide_${currentSlideIndex + 1}.html`;
          link.href = URL.createObjectURL(blob);
          link.click();
          URL.revokeObjectURL(link.href);
        }}>Export HTML</button>
      </div>
    </div>

    <div class="flex-grow p-4 md:p-8 flex items-center justify-center overflow-hidden relative">
      <div class="w-full h-full max-w-5xl bg-white rounded shadow-2xl border border-ge-border overflow-hidden relative neumorphic" style="aspect-ratio: 16/9;">

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
                    .replace(/\\n/g, '\n').replace(/\\"/g, '"');
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

      </div>
    </div>

    <div class="h-14 border-t border-ge-border flex items-center justify-center gap-4 bg-ge-card/50">
      <button
        class="px-4 py-1.5 rounded border border-ge-border bg-ge-bg hover:bg-ge-border transition-colors disabled:opacity-50"
        disabled={slides.length === 0 || currentSlideIndex <= 0}
        on:click={() => { if (currentSlideIndex > 0) { currentSlideIndex--; iframeSrcDoc = slides[currentSlideIndex].html; } }}
      >Prev</button>
      <span class="text-sm font-mono text-ge-text-muted">Slide {slides.length ? currentSlideIndex + 1 : 0} of {slides.length}</span>
      <button
        class="px-4 py-1.5 rounded border border-ge-border bg-ge-border hover:bg-ge-border transition-colors disabled:opacity-50"
        disabled={slides.length === 0 || currentSlideIndex >= slides.length - 1}
        on:click={() => { if (currentSlideIndex < slides.length - 1) { currentSlideIndex++; iframeSrcDoc = slides[currentSlideIndex].html; } }}
      >Next</button>
    </div>
  </div>

  <!-- Saved Slides / Past Classes Modal -->
  {#if isSavedModalOpen}
  <div class="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-4">
    <div class="bg-ge-card border border-ge-border rounded-xl shadow-2xl w-full max-w-3xl max-h-[85vh] flex flex-col overflow-hidden">
      <div class="p-4 border-b border-ge-border flex justify-between items-center bg-ge-bg">
        <div class="flex items-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-ge-accent"><path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"/></svg>
          <h2 class="text-lg font-bold font-raleway text-ge-text">Past Classes & Saved Slides</h2>
          <span class="text-xs px-2 py-0.5 rounded-full bg-ge-border text-ge-text-muted font-mono">{filteredSavedSlides.length} items</span>
        </div>
        <button
          class="text-ge-text-muted hover:text-ge-text p-1.5 rounded-lg hover:bg-ge-border transition-colors"
          on:click={() => isSavedModalOpen = false}
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>

      <div class="p-4 border-b border-ge-border bg-ge-card flex gap-3 items-center">
        <div class="relative flex-grow">
          <input
            type="text"
            bind:value={savedSearchQuery}
            placeholder="Search classes, lessons, topics, or dates..."
            class="w-full bg-ge-bg border border-ge-border rounded-lg px-3 py-2 pl-9 text-sm text-ge-text placeholder:text-ge-text-muted/50 focus:border-ge-accent outline-none"
          />
          <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="absolute left-3 top-3 text-ge-text-muted/60"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        </div>
        <button
          class="px-3 py-2 text-xs bg-ge-bg border border-ge-border rounded-lg hover:bg-ge-border text-ge-text transition-colors flex items-center gap-1.5"
          on:click={loadSavedSlides}
          disabled={isLoadingSaved}
        >
          <span class:animate-spin={isLoadingSaved}>↻</span>
          Refresh
        </button>
      </div>

      <div class="flex-grow overflow-y-auto p-4 space-y-2 max-h-[55vh]">
        {#if isLoadingSaved && savedSlides.length === 0}
          <div class="text-center py-12 text-ge-text-muted text-sm flex flex-col items-center gap-2">
            <span class="animate-spin h-5 w-5 border-2 border-ge-accent border-t-transparent rounded-full"></span>
            Loading saved classes...
          </div>
        {:else if filteredSavedSlides.length === 0}
          <div class="text-center py-12 text-ge-text-muted text-sm">
            {savedSearchQuery ? `No saved slides matching "${savedSearchQuery}"` : 'No saved slides found in saved_slides/'}
          </div>
        {:else}
          <div class="grid grid-cols-1 md:grid-cols-2 gap-2.5">
            {#each filteredSavedSlides as slide}
              <button
                class="text-left p-3.5 rounded-lg border border-ge-border bg-ge-bg hover:border-ge-accent hover:bg-ge-card transition-all group flex flex-col justify-between"
                on:click={() => selectSavedSlide(slide)}
              >
                <div>
                  <div class="font-medium text-sm text-ge-text group-hover:text-ge-accent line-clamp-2 transition-colors">
                    {slide.title}
                  </div>
                  <div class="text-xs text-ge-text-muted/70 truncate mt-1 font-mono">
                    {slide.filename}
                  </div>
                </div>
                <div class="flex items-center justify-between mt-3 text-xs text-ge-text-muted border-t border-ge-border/50 pt-2">
                  <span>{slide.date} • {(slide.size / 1024).toFixed(1)} KB</span>
                  <span class="text-ge-accent font-medium group-hover:underline">Load Slide →</span>
                </div>
              </button>
            {/each}
          </div>
        {/if}
      </div>

      <div class="p-3 bg-ge-bg border-t border-ge-border flex justify-between items-center text-xs text-ge-text-muted">
        <span>Click any past class to load it directly into the preview stage.</span>
        <button
          class="px-4 py-1.5 bg-ge-card border border-ge-border rounded hover:bg-ge-border text-ge-text transition-colors"
          on:click={() => isSavedModalOpen = false}
        >
          Close
        </button>
      </div>
    </div>
  </div>
  {/if}

</main>
