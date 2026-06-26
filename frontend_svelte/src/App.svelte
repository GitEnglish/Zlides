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

  import * as ChainOfThought from '$lib/components/ai-elements/chain-of-thought';


  let cost = 0.00;
  let isGenerating = false;
  let isBatchMode = false;
  let isUploading = false;
  let status = "Ready";

  let slides: any[] = [];
  let currentSlideIndex = 0;
  // Included a mock RR button to prove the concept works when dropped in
  let iframeSrcDoc = "<html><body style='display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;background:#131313;color:#888;font-family:sans-serif;margin:0;'><div style='text-align:center;'><h3>Zlides V2 Preview</h3><p style='font-size:12px;color:#555;'>Your generated presentation will appear here.</p></div></body></html>";

  let promptText = "";
  let files: FileList | null = null;
  let extractedMarkdown = "";
  let uploadMode = "content"; // 'content' or 'style'

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
    if (isGenerating) return;
    if (!promptText.trim() && !files && !extractedMarkdown) {
      if (slides.length === 0) {
        cost = 0;
      }
      return;
    }
    try {
      const res = await fetch("/estimate-cost", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: promptText + (extractedMarkdown || ""),
          files_attached: files ? files.length : 0,
          format: selectedFormat,
          page_count: pageCount
        })
      });
      const data = await res.json();
      cost = data.cost_usd;
    } catch (e) {
      console.error(e);
    }
  }

  $: {
    promptText;
    extractedMarkdown;
    files;
    selectedFormat;
    pageCount;
    updateCost();
  }
  $: isBatchMode = promptText.toLowerCase().includes("batch") || promptText.includes("\n\n");

  async function handleFileSelect(e: Event) {
    const target = e.target as HTMLInputElement;
    if (target.files && target.files.length > 0) {
      files = target.files;
      isUploading = true;
      status = `Ingesting ${files[0].name} via File Parser API...`;

      const formData = new FormData();
      formData.append("file", files[0]);

      formData.append("type", uploadMode);

      try {
        const res = await fetch("/upload", { method: "POST", body: formData });
        const data = await res.json();

        extractedMarkdown = data.parsed_markdown || "";

        if (data.style_extracted) {
          status = `Reverse engineered style "${data.style_extracted.name}" saved!`;
          // Dynamically add to availableStyles so it shows up in Style Theme dropdown instantly
          availableStyles = [
            ...availableStyles,
            {
              id: data.style_extracted.id,
              name: data.style_extracted.name,
              preview_colors: data.style_extracted.preview_colors || [],
              brand_png: data.style_extracted.brand_png
            }
          ];
          selectedStyle = data.style_extracted.id;
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

    // Estimate input cost dynamically
    const combinedInputText = textToSend + (extractedMarkdown ? "\n\n" + extractedMarkdown : "");
    const estimatedInputTokens = (combinedInputText.split(/\s+/).filter(Boolean).length) * 1.5 + (files ? files.length * 3000 : 0);
    const inputCostRmb = (estimatedInputTokens / 1000000.0) * 0.8;
    const initialInputCost = inputCostRmb * 2.5 * 0.14;
    cost = initialInputCost;
    let totalOutputChars = 0;

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

                // Accumulate output characters for live cost ticker
                let chunkChars = 0;
                if (data.text) chunkChars += data.text.length;
                if (data.html && data.type !== 'final_html') chunkChars += data.html.length;
                
                if (chunkChars > 0) {
                  totalOutputChars += chunkChars;
                  const liveOutputTokens = totalOutputChars / 2.5;
                  const outputCostRmb = (liveOutputTokens / 1000000.0) * 2.0;
                  const liveOutputCost = outputCostRmb * 2.5 * 0.14;
                  cost = initialInputCost + liveOutputCost;
                }

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
                  if (data.tool) {
                    toolCalls = [...toolCalls, { name: data.tool, input: `Render slide page at position ${data.position || ''}` }];
                  }
                  liveHtmlChunks.push(data.html || '');
                  renderLiveHtmlChunks();
                }

                if (data.type === 'slide_remove') {
                  console.log("Removing slides at positions:", data.positions);
                  if (data.tool) {
                    toolCalls = [...toolCalls, { name: data.tool, input: `Remove slides at positions ${data.positions || ''}` }];
                  }
                }

                if (data.type === 'slide_replace') {
                  if (thinkingBuffer.trim()) {
                    thoughts = [...thoughts, thinkingBuffer.trim()];
                    thinkingBuffer = '';
                  }
                  if (data.tool) {
                    toolCalls = [...toolCalls, { name: data.tool, input: `Replace slide at position ${data.position || ''}` }];
                  }
                  liveHtmlChunks.push(data.html || '');
                  renderLiveHtmlChunks();
                }

                if (data.type === 'slide_navigate') {
                  if (data.position && data.position.length > 0) {
                    currentSlideIndex = Math.max(0, data.position[0] - 1);
                  }
                  if (data.tool) {
                    toolCalls = [...toolCalls, { name: data.tool, input: `Navigate to position ${data.position || ''}` }];
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

  <div class="w-full md:w-[400px] p-4 flex flex-col gap-3 bg-ge-card border-r border-ge-border shadow-2xl z-10 flex-shrink-0 relative overflow-y-auto">
    <div class="space-y-1 flex-shrink-0">
      <div class="flex items-center gap-2 flex-wrap">
        <h1 class="text-2xl font-bold tracking-tight text-ge-accent font-raleway">Zlides V2</h1>
        {#if isBatchMode}
          <span class="bg-ge-bg text-[10px] px-1.5 py-0.5 rounded border border-ge-border text-ge-accent animate-pulse">Batch Mode</span>
        {:else}
          <span class="bg-ge-bg text-[10px] px-1.5 py-0.5 rounded border border-ge-border text-ge-text-muted">Mongoose Fast</span>
        {/if}
        <span class="bg-ge-bg text-[10px] px-1.5 py-0.5 rounded border border-ge-border text-ge-success font-mono font-bold" title="Estimated Cost">
          ${cost.toFixed(3)}
        </span>
        <span class="relative flex h-2 w-2 ml-1" title={isGenerating || isUploading ? 'Processing...' : 'Ready'}>
          {#if isGenerating || isUploading}
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-gradient-to-r from-red-700 to-orange-500 opacity-75"></span>
            <span class="relative inline-flex rounded-full h-2 w-2 bg-gradient-to-r from-red-700 to-orange-500"></span>
          {:else}
            <span class="relative inline-flex rounded-full h-2 w-2 bg-ge-success"></span>
          {/if}
        </span>
      </div>
      <p class="text-ge-text-muted text-xs">Drop vibes. Get slides.</p>
    </div>

    <!-- UI Controls -->
    <div class="flex flex-col gap-2 flex-shrink-0 text-xs">
      <div class="grid grid-cols-3 gap-1.5">
        <div class="flex items-center gap-1 bg-ge-bg border border-ge-border rounded px-2 py-1 text-ge-text-muted focus-within:border-ge-accent">
          <span class="text-[9px] font-mono uppercase font-bold tracking-wider select-none text-ge-text-muted/65">Fmt</span>
          <select bind:value={selectedFormat} class="bg-transparent border-none text-ge-text outline-none focus:outline-none focus:ring-0 cursor-pointer w-full text-xs p-0 min-w-0">
            {#each ["slides", "poster", "worksheet", "report", "rr"] as fmt}
              <option value={fmt} class="bg-ge-card text-ge-text">{fmt}</option>
            {/each}
          </select>
        </div>

        <div class="flex items-center gap-1 bg-ge-bg border border-ge-border rounded px-2 py-1 text-ge-text-muted focus-within:border-ge-accent">
          <span class="text-[9px] font-mono uppercase font-bold tracking-wider select-none text-ge-text-muted/65">Style</span>
          <select bind:value={selectedStyle} class="bg-transparent border-none text-ge-text outline-none focus:outline-none focus:ring-0 cursor-pointer w-full text-xs p-0 min-w-0">
            {#each availableStyles as style}
              <option value={style.id} class="bg-ge-card text-ge-text">{style.name}</option>
            {/each}
          </select>
        </div>

        <div class="flex items-center gap-1 bg-ge-bg border border-ge-border rounded px-2 py-1 text-ge-text-muted focus-within:border-ge-accent">
          <span class="text-[9px] font-mono uppercase font-bold tracking-wider select-none text-ge-text-muted/65">Pages</span>
          <input type="number" bind:value={pageCount} min="1" max="20" class="bg-transparent border-none text-ge-text outline-none focus:outline-none focus:ring-0 w-full text-xs p-0 min-w-0" title="Page Count">
        </div>
      </div>
    </div>

    <!-- Chat History -->
    <div id="chat-history" class="flex-grow overflow-y-auto flex flex-col gap-2.5 p-3 bg-ge-bg/30 rounded-lg border border-ge-border/40 relative text-sm neumorphic-inset">
      {#each chatMessages as msg}
        {#if msg.role !== 'thinking'}
        <div class="p-2.5 rounded-lg max-w-[85%] whitespace-pre-wrap {msg.role === 'user' ? 'bg-ge-card text-ge-text ml-auto border border-ge-border/60 shadow-sm' : 'bg-ge-bg/55 text-ge-text-muted mr-auto border border-ge-border/30'}">
          {#if msg.role !== 'user'}
            <div class="text-[9px] font-mono font-bold mb-1 text-ge-accent uppercase tracking-wider select-none">Z.AI Agent</div>
          {/if}
          {#if msg.role === 'agent' || msg.role === 'thinking'}
            <div class="prose prose-invert prose-sm max-w-none text-ge-text-muted">
              <SvelteMarkdown source={msg.text} extensions={[markedMermaid()]} {renderers} />
            </div>
          {:else}
            <div class="text-ge-text text-xs">{msg.text}</div>
          {/if}
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
      <div class="flex flex-col bg-ge-bg rounded-lg p-2.5 border border-ge-border neumorphic-inset relative min-h-[140px] flex-shrink-0">
        <textarea
          bind:value={promptText}
          on:keydown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); generate(); } }}
          placeholder="Describe your vibe... (e.g. 'Turn this uploaded PDF into slides.')"
          class="w-full flex-grow bg-transparent border-none outline-none resize-none p-1 pb-10 text-ge-text placeholder:text-ge-text-muted/50 text-sm"
        ></textarea>

        <!-- Floating action buttons at the bottom of the input container -->
        <div class="absolute bottom-2 left-2 right-2 flex justify-between items-center pointer-events-none">
           <div class="flex items-center gap-1.5 pointer-events-auto">
             <label class="cursor-pointer p-1.5 rounded bg-ge-card hover:bg-ge-border text-ge-text hover:text-ge-accent border border-ge-border transition-colors disabled:opacity-50 flex items-center justify-center h-7 w-7" title="Ingest Document or Style Image" class:opacity-50={isUploading}>
               {#if isUploading}
                 <span class="animate-spin h-3.5 w-3.5 border-2 border-ge-accent border-t-transparent rounded-full"></span>
               {:else}
                 <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>
               {/if}
               <input type="file" class="hidden" on:change={handleFileSelect} accept=".pdf,.png,.jpg,.jpeg,.doc,.docx" disabled={isUploading} />
             </label>

             <select bind:value={uploadMode} class="bg-ge-card border border-ge-border rounded px-1.5 py-0.5 text-[10px] text-ge-text-muted outline-none focus:border-ge-accent cursor-pointer h-7 select-none">
               <option value="content" class="bg-ge-card text-ge-text">Remake Content</option>
               <option value="style" class="bg-ge-card text-ge-text">Harvest Style</option>
             </select>
           </div>

            <div class="flex items-center gap-2 pointer-events-auto">
              {#if files}
                <span class="text-[11px] bg-ge-card border border-ge-border px-2 py-0.5 rounded text-ge-accent truncate max-w-[150px]" title={files[0].name}>{files[0].name}</span>
              {/if}
              {#if isGenerating}
                <button on:click={stopRequest} class="bg-ge-danger text-ge-bg font-bold px-3 py-1 rounded text-xs hover:opacity-90 transition-all flex items-center gap-1 h-7 animate-pulse">
                  <span class="h-1.5 w-1.5 bg-ge-bg rounded-sm"></span> Stop
                </button>
              {:else}
                <button
                  on:click={generate}
                  disabled={!promptText.trim() && !extractedMarkdown}
                  class="bg-ge-accent text-ge-bg rounded flex items-center justify-center h-7 w-7 hover:opacity-90 transition-all disabled:opacity-50 border border-ge-border/20 shadow-sm"
                  title="Send Command"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
                </button>
              {/if}
            </div>
        </div>
      </div>
    </div>
  </div>

  <div class="flex-grow bg-ge-bg relative flex flex-col">
    <div class="h-12 border-b border-ge-border flex justify-between items-center px-4 bg-ge-card/50">
      <div class="text-xs font-raleway font-bold text-ge-accent">Preview</div>
      
      <!-- Slide controls in the center -->
      <div class="flex items-center gap-2 text-xs">
        <button
          class="p-1 rounded border border-ge-border bg-ge-bg hover:bg-ge-border transition-colors disabled:opacity-50 flex items-center justify-center h-7 w-7 text-ge-text"
          disabled={slides.length === 0 || currentSlideIndex <= 0}
          on:click={() => { if (currentSlideIndex > 0) { currentSlideIndex--; iframeSrcDoc = slides[currentSlideIndex].html; } }}
          title="Previous Slide"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m15 18-6-6 6-6"/></svg>
        </button>
        <span class="font-mono text-ge-text-muted select-none min-w-[70px] text-center">
          {slides.length ? currentSlideIndex + 1 : 0} / {slides.length}
        </span>
        <button
          class="p-1 rounded border border-ge-border bg-ge-bg hover:bg-ge-border transition-colors disabled:opacity-50 flex items-center justify-center h-7 w-7 text-ge-text"
          disabled={slides.length === 0 || currentSlideIndex >= slides.length - 1}
          on:click={() => { if (currentSlideIndex < slides.length - 1) { currentSlideIndex++; iframeSrcDoc = slides[currentSlideIndex].html; } }}
          title="Next Slide"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"/></svg>
        </button>
      </div>

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
      <div class="w-full h-full max-w-5xl bg-transparent rounded shadow-2xl border border-ge-border/30 overflow-hidden relative" style="aspect-ratio: 16/9;">
        <iframe
          bind:this={iframeElement}
          title="Slide Preview"
          srcdoc={iframeSrcDoc}
          class="w-full h-full bg-transparent"
          sandbox="allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox"
        ></iframe>
      </div>
    </div>
  </div>

</main>
