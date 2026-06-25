<script lang="ts">
  import { onMount } from 'svelte';

  import * as ChainOfThought from '$lib/components/ai-elements/chain-of-thought';


  let cost = 0.00;
  let isGenerating = false;
  let isBatchMode = false;
  let isUploading = false;
  let status = "Ready";

  let slides: any[] = [];
  let currentSlideIndex = 0;
  // Included a mock RR button to prove the concept works when dropped in
  let iframeSrcDoc = "<html><body style='display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;background:#262424;color:#9e9e9e;font-family:sans-serif;'><h3>Zlides V2 Preview</h3><p>Example RR Student Exercise below:</p><br><button id='regenerate' data-prompt='Give me a new math problem' style='padding:8px 16px;background:#ff6600;color:#fff;border:none;border-radius:4px;cursor:pointer;'>Regenerate Exercise</button><script>document.querySelectorAll('button[id=\"regenerate\"]').forEach(b=>b.addEventListener('click',function(){window.parent.postMessage({type:'regenerate',prompt:this.getAttribute('data-prompt')},'*');this.innerText='Regenerating...';}));<\/script></body></html>";

  let promptText = "";
  let files: FileList | null = null;
  let extractedMarkdown = "";

  onMount(async () => {
    // Load styles from the backend
    try {
      const resp = await fetch("/styles");
      availableStyles = await resp.json();
    } catch (e) {
      console.warn("Could not load styles:", e);
    }

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


  let isThinking = false;
  let thoughts: string[] = [];

  let toolCalls: { name: string, input: string }[] = [];
  let currentToolBuffer = '';
  let currentToolName = '';

let currentController: AbortController | null = null;
  let liveHtmlChunks: string[] = [];
  let iframeElement: HTMLIFrameElement | null = null;
  let thinkingBuffer = '';

  // We'll define these fully in Step 3, but provide stubs to make TS happy
  let chatMessages: any[] = [{ role: "agent", text: "Ready! Pick a format + style, describe what you want." }];
  let selectedFormat = "slides";
  let selectedStyle = "auto";
  let pageCount = 5;
  let slideLayout = "";
  let availableStyles: any[] = [];


  function extractImages(thought: string) {
    const images = [];
    const regex = /!\[(.*?)\]\((.*?)\)/g;
    let match;
    while ((match = regex.exec(thought)) !== null) {
      images.push({ alt: match[1], url: match[2] });
    }
    return images;
  }

  function stripImages(thought: string) {
    return thought.replace(/!\[(.*?)\]\((.*?)\)/g, '').trim();
  }


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


    currentController = new AbortController();
    liveHtmlChunks = [];
    thinkingBuffer = '';
    thoughts = [];
    toolCalls = [];
    currentToolBuffer = '';
    currentToolName = '';
    isThinking = true;

    try {
      const response = await fetch('/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: textToSend + (extractedMarkdown ? "\n\n" + extractedMarkdown : ""),
          format: selectedFormat,
          style: selectedStyle,
          page_count: pageCount,
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

                  // Simple heuristic: if we hit a newline or sentence end, push a thought.
                  if (thinkingBuffer.match(/[\.\n]/)) {
                      let sentences = thinkingBuffer.split(/(?<=[\.\n])/);
                      for (let i = 0; i < sentences.length - 1; i++) {
                         let s = sentences[i].trim();
                         if (s) thoughts = [...thoughts, s];
                      }
                      thinkingBuffer = sentences[sentences.length - 1];
                  } else if (thinkingBuffer.length > 50) {
                      // fallback if no punctuation but long text
                      thoughts = [...thoughts, thinkingBuffer.trim()];
                      thinkingBuffer = '';
                  }
                }

                                if (data.type === 'tool') {
                  if (data.tool_name) {
                     // Flush previous
                     if (currentToolName && currentToolBuffer) {
                         toolCalls = [...toolCalls, { name: currentToolName, input: currentToolBuffer }];
                     }
                     currentToolName = data.tool_name;
                     currentToolBuffer = data.input || '';
                  } else if (data.input) {
                     currentToolBuffer += data.input;
                  }

                  // In some stream representations it comes in as raw tool blocks, just handle generic JSON representations
                  try {
                      if (data.text) {
                         let parsed = JSON.parse(data.text);
                         if (parsed.tool_name) {
                             toolCalls = [...toolCalls, { name: parsed.tool_name, input: parsed.input || '' }];
                         }
                      }
                  } catch (e) {}
                }

                if (data.type === 'answer' || data.type === 'slide_page' || data.type === 'final_html' || data.type === 'error') {
                   // Flush pending tool
                   if (currentToolName && currentToolBuffer) {
                       toolCalls = [...toolCalls, { name: currentToolName, input: currentToolBuffer }];
                       currentToolName = '';
                       currentToolBuffer = '';
                   }
                }

                if (data.type === 'answer') {
                  if (thinkingBuffer.trim()) {
                    thoughts = [...thoughts, thinkingBuffer.trim()];
                    thinkingBuffer = '';
                  }
                  isThinking = false;

                  const lastMsg = chatMessages[chatMessages.length - 1];
                  if (lastMsg && lastMsg.role === 'agent') {
                    lastMsg.text += data.text;
                    chatMessages = [...chatMessages];
                  } else {
                    addMessage(data.text, 'agent');
                  }
                }

                if (data.type === 'slide_page') {
                  if (thinkingBuffer.trim()) {
                    thoughts = [...thoughts, thinkingBuffer.trim()];
                    thinkingBuffer = '';
                  }
                  liveHtmlChunks.push(data.html || '');
                  renderLiveHtmlChunks();
                }

                if (data.type === 'slide_remove') {
                  console.log("Removing slides at positions:", data.positions);
                }

                if (data.type === 'slide_replace') {
                  if (thinkingBuffer.trim()) {
                    thoughts = [...thoughts, thinkingBuffer.trim()];
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
                  if (thinkingBuffer.trim()) {
                    thoughts = [...thoughts, thinkingBuffer.trim()];
                    thinkingBuffer = '';
                  }

isThinking = false;

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
                  if (thinkingBuffer.trim()) {
                    thoughts = [...thoughts, thinkingBuffer.trim()];
                    thinkingBuffer = '';
                  }

isThinking = false;
                  addMessage('Error: ' + data.text, 'agent');
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
isThinking = false;
      } else {
        status = 'Error: ' + err.message;
        addMessage('Connection error — is the server running?', 'agent');
      }
    } finally {
      isGenerating = false;
      currentController = null;
    }
  }
</script>

<main class="min-h-screen bg-ge-bg text-ge-text flex flex-col md:flex-row h-screen overflow-hidden">

  <div class="w-full md:w-6/12 p-6 flex flex-col gap-4 bg-ge-card border-r border-ge-border shadow-2xl z-10 flex-shrink-0 relative overflow-y-auto">
    <div class="space-y-2 flex-shrink-0">
      <div class="flex items-center gap-2">
        <h1 class="text-3xl font-bold tracking-tight text-ge-accent font-raleway">Zlides V2</h1>
        {#if isBatchMode}
          <span class="bg-ge-bg text-xs px-2 py-1 rounded border border-ge-border text-ge-accent animate-pulse">Batch Mode</span>
        {:else}
          <span class="bg-ge-bg text-xs px-2 py-1 rounded border border-ge-border text-ge-text-muted">Mongoose Fast</span>
        {/if}
      </div>
      <p class="text-ge-text-muted text-sm">Drop vibes. Get slides. The smart parser extracts layout + style from uploaded files.</p>
    </div>

    <!-- UI Controls -->
    <div class="flex flex-col gap-2 flex-shrink-0 text-sm">
      <div class="flex gap-2 flex-wrap">
        {#each ["slides", "poster", "worksheet", "report", "rr"] as fmt}
          <button
            class="px-3 py-1 rounded-full border border-ge-border transition-colors {selectedFormat === fmt ? 'bg-gradient-to-r from-red-700 to-orange-500 text-white font-bold border-transparent' : 'bg-ge-bg text-ge-text hover:bg-ge-border'}"
            on:click={() => selectedFormat = fmt}
          >
            {fmt}
          </button>
        {/each}
      </div>

      <div class="flex gap-2 flex-wrap mt-2">
        {#each availableStyles as style}
          <button
            class="px-3 py-1 rounded-full border border-ge-border transition-colors text-xs {selectedStyle === style.id ? 'bg-gradient-to-r from-red-700 to-orange-500 text-white font-bold border-transparent' : 'bg-ge-bg text-ge-text hover:bg-ge-border'}"
            on:click={() => selectedStyle = style.id}
          >
            {style.name}
          </button>
        {/each}
      </div>

      <div class="flex gap-2 mt-2">
        <input type="number" bind:value={pageCount} min="1" max="20" class="bg-ge-bg border border-ge-border rounded px-2 py-1 w-20 text-ge-text outline-none" title="Page Count">
        <select bind:value={slideLayout} class="bg-ge-bg border border-ge-border rounded px-2 py-1 text-ge-text flex-grow outline-none">
          <option value="">Layout: Auto</option>
          <option value="title-content">Title+Content</option>
          <option value="two-column">Two Column</option>
        </select>
      </div>
    </div>

    <!-- Chat History -->
    <div id="chat-history" class="flex-grow overflow-y-auto flex flex-col gap-2 p-2 bg-ge-bg rounded-lg border border-ge-border relative neumorphic-inset text-sm">
      {#each chatMessages as msg}
        {#if msg.role !== 'thinking'}
        <div class="p-2 rounded max-w-[90%] whitespace-pre-wrap {msg.role === 'user' ? 'bg-ge-card text-ge-text ml-auto border border-ge-border' : 'bg-transparent text-ge-text-muted mr-auto'}">
          {#if msg.role !== 'user'}
            <div class="text-xs font-bold mb-1 text-ge-accent">Z.AI Agent</div>
          {/if}
          {msg.text}
        </div>
        {/if}
      {/each}

      {#if thoughts.length > 0 || isThinking}
        <div class="p-2 rounded max-w-[90%] w-full bg-transparent text-ge-text-muted mr-auto">
          <ChainOfThought.Root open={isThinking} defaultOpen={true}>
            <ChainOfThought.Header />
            <ChainOfThought.Content>
              {#each thoughts as thought, i}
                <ChainOfThought.Step
                  label={stripImages(thought) || "Looking at image..."}
                  status={i === thoughts.length - 1 && isThinking ? "active" : "complete"}
                >
                  {#each extractImages(thought) as img}
                    <ChainOfThought.Image caption={img.alt}>
                      <img src={img.url} alt={img.alt} class="w-full h-auto rounded" />
                    </ChainOfThought.Image>
                  {/each}
                </ChainOfThought.Step>
              {/each}

              {#if toolCalls.length > 0}
                <ChainOfThought.SearchResults class="mt-2">
                  {#each toolCalls as call}
                    <ChainOfThought.SearchResult>{call.name}: {call.input.length > 20 ? call.input.substring(0,20)+'...' : call.input}</ChainOfThought.SearchResult>
                  {/each}
                </ChainOfThought.SearchResults>
              {/if}
              {#if isThinking && thoughts.length === 0}

                 <ChainOfThought.Step label="Initializing thought process..." status="active" />
              {/if}
            </ChainOfThought.Content>
          </ChainOfThought.Root>
        </div>
      {/if}
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

      <div class="p-1 px-3 bg-ge-bg rounded-md font-mono text-[10px] border border-ge-border flex justify-between items-center">
        <span class="text-ge-text-muted flex items-center gap-2">
          <span class="relative flex h-2 w-2">
            {#if isGenerating || isUploading}
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-gradient-to-r from-red-700 to-orange-500 opacity-75"></span>
            <span class="relative inline-flex rounded-full h-2 w-2 bg-gradient-to-r from-red-700 to-orange-500"></span>
            {:else}
            <span class="relative inline-flex rounded-full h-2 w-2 bg-ge-success"></span>
            {/if}
          </span>
          Estimated Cost
        </span>
        <span class="text-ge-success font-bold text-xs">${cost.toFixed(3)} USD</span>
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
            class="flex-grow bg-gradient-to-r from-red-700 to-orange-500 text-ge-bg font-bold py-3 rounded-lg hover:opacity-90 transition-colors shadow-lg disabled:opacity-50 disabled:cursor-not-allowed">
            {isGenerating ? (isBatchMode ? 'Batching...' : 'Generating...') : (isBatchMode ? 'Schedule Batch' : 'Generate')}
          </button>
        {/if}
      </div>
      <div class="text-center text-xs text-ge-text-muted font-mono h-4 truncate">{status}</div>
    </div>
  </div>

  <div class="flex-grow bg-ge-bg relative flex flex-col">
    <div class="h-12 border-b border-ge-border flex justify-between items-center px-4 bg-ge-card/50">
      <div class="text-xs font-raleway font-bold">Preview Stage (RR Enabled)</div>
      <div class="flex gap-2">
        <button class="text-xs px-3 py-1 bg-ge-bg border border-ge-border rounded hover:bg-ge-border transition-colors" on:click={() => window.print()}>Export PDF</button>
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
        class="px-4 py-1.5 rounded border border-ge-border bg-ge-bg hover:bg-ge-border transition-colors disabled:opacity-50"
        disabled={slides.length === 0 || currentSlideIndex >= slides.length - 1}
        on:click={() => { if (currentSlideIndex < slides.length - 1) { currentSlideIndex++; iframeSrcDoc = slides[currentSlideIndex].html; } }}
      >Next</button>
    </div>
  </div>

</main>
