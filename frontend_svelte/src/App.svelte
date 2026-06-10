<script lang="ts">
  import { onMount } from 'svelte';

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

  onMount(() => {
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
    } else {
      status = "Generating (Mongoose Fast)...";
      setTimeout(() => {
        status = "Ready";
      }, 2000);
    }

    isGenerating = false;
  }
</script>

<main class="min-h-screen bg-ge-bg text-ge-text flex flex-col md:flex-row h-screen overflow-hidden">

  <div class="w-full md:w-1/3 p-6 flex flex-col gap-6 bg-ge-card border-r border-ge-border shadow-2xl z-10 flex-shrink-0">
    <div class="space-y-2">
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

    <div class="flex-grow flex flex-col gap-4">
      <div class="flex-grow flex flex-col bg-ge-bg rounded-lg p-2 border border-ge-border relative neumorphic-inset">
        <textarea
          bind:value={promptText}
          placeholder="Describe your vibe... (e.g. 'Turn this uploaded PDF into slides. Match the style.')"
          class="w-full h-full bg-transparent border-none outline-none resize-none p-2 text-ge-text placeholder:text-ge-text-muted/50"
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
        <button
          on:click={generate}
          disabled={isGenerating || isUploading}
          class="flex-grow bg-ge-accent text-ge-bg font-bold py-3 rounded-lg hover:bg-ge-accent-hover transition-colors shadow-lg hover:shadow-ge-accent/20 disabled:opacity-50 disabled:cursor-not-allowed">
          {isGenerating ? (isBatchMode ? 'Batching...' : 'Generating...') : (isBatchMode ? 'Schedule Batch' : 'Generate')}
        </button>
      </div>
      <div class="text-center text-xs text-ge-text-muted font-mono h-4 truncate">{status}</div>
    </div>
  </div>

  <div class="flex-grow bg-ge-bg relative flex flex-col">
    <div class="h-12 border-b border-ge-border flex justify-between items-center px-4 bg-ge-card/50">
      <div class="text-sm font-raleway font-bold">Preview Stage (RR Enabled)</div>
      <div class="flex gap-2">
        <button class="text-xs px-3 py-1 bg-ge-bg border border-ge-border rounded hover:bg-ge-border transition-colors">Export PDF</button>
        <button class="text-xs px-3 py-1 bg-ge-bg border border-ge-border rounded hover:bg-ge-border transition-colors">Export HTML</button>
      </div>
    </div>

    <div class="flex-grow p-4 md:p-8 flex items-center justify-center overflow-hidden relative">
      <div class="w-full h-full max-w-5xl bg-white rounded shadow-2xl border border-ge-border overflow-hidden relative neumorphic" style="aspect-ratio: 16/9;">
        <iframe
          title="Slide Preview"
          srcdoc={iframeSrcDoc}
          class="w-full h-full bg-white"
          sandbox="allow-scripts allow-same-origin allow-popups"
        ></iframe>
      </div>
    </div>

    <div class="h-14 border-t border-ge-border flex items-center justify-center gap-4 bg-ge-card/50">
      <button class="px-4 py-1.5 rounded border border-ge-border bg-ge-bg hover:bg-ge-border transition-colors disabled:opacity-50">Prev</button>
      <span class="text-sm font-mono text-ge-text-muted">Slide {slides.length ? currentSlideIndex + 1 : 0} of {slides.length}</span>
      <button class="px-4 py-1.5 rounded border border-ge-border bg-ge-bg hover:bg-ge-border transition-colors disabled:opacity-50">Next</button>
    </div>
  </div>

</main>
