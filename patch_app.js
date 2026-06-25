const fs = require('fs');

const appPath = 'frontend_svelte/src/App.svelte';
let code = fs.readFileSync(appPath, 'utf-8');

// Imports
const importAddition = `
  import * as ChainOfThought from '$lib/components/ai-elements/chain-of-thought';
`;
code = code.replace("import { onMount } from 'svelte';", "import { onMount } from 'svelte';\n" + importAddition);

// State
const stateAddition = `
  let isThinking = false;
  let thoughts: string[] = [];
`;
code = code.replace("let currentController: AbortController | null = null;", stateAddition + "let currentController: AbortController | null = null;");

// Update generating
code = code.replace("liveHtmlChunks = [];\n    thinkingBuffer = '';", "liveHtmlChunks = [];\n    thinkingBuffer = '';\n    thoughts = [];\n    isThinking = true;");

// Fix thinking logic
// Replace the big `if (data.type === 'thinking')` block.
// Let's use string replace for the whole section inside the streaming loop
const regexThinking = /if \(data\.type === 'thinking'\) \{([\s\S]*?)if \(data\.type === 'answer'\) \{/m;

const newThinking = `if (data.type === 'thinking') {
                  thinkingBuffer += data.text;

                  // Simple heuristic: if we hit a newline or sentence end, push a thought.
                  if (thinkingBuffer.match(/[\\.\\n]/)) {
                      let sentences = thinkingBuffer.split(/(?<=[\\.\\n])/);
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

                if (data.type === 'answer') {`;

code = code.replace(regexThinking, newThinking);

// Clean up answer and final_html removing the thinkingBuffer flush to chatMessages
// For answer:
code = code.replace(
  `                  if (thinkingBuffer) {
                    const lastMsg = chatMessages[chatMessages.length - 1];
                    if (lastMsg && lastMsg.role === 'thinking') {
                      lastMsg.text = lastMsg.text === '[Thinking...]' ? thinkingBuffer : lastMsg.text + thinkingBuffer;
                    }
                    thinkingBuffer = '';
                  }`,
  `                  if (thinkingBuffer.trim()) {
                    thoughts = [...thoughts, thinkingBuffer.trim()];
                    thinkingBuffer = '';
                  }
                  isThinking = false;`
);

// For other sections doing the same:
const oldFlush = `                  if (thinkingBuffer) {
                    const lastMsg = chatMessages[chatMessages.length - 1];
                    if (lastMsg && lastMsg.role === 'thinking') {
                      lastMsg.text = lastMsg.text === '[Thinking...]' ? thinkingBuffer : lastMsg.text + thinkingBuffer;
                    }
                    thinkingBuffer = '';
                  }`;
const newFlush = `                  if (thinkingBuffer.trim()) {
                    thoughts = [...thoughts, thinkingBuffer.trim()];
                    thinkingBuffer = '';
                  }`;
code = code.split(oldFlush).join(newFlush);

// Remove the conversion of thinking message to agent message
const conversionBlock = `                  // Convert thinking message to agent message if it was just thinking
                  const lastMsg = chatMessages[chatMessages.length - 1];
                  if (lastMsg && lastMsg.role === 'thinking') {
                    lastMsg.text = \`[Complete — \${selectedFormat} / \${selectedStyle}]\`;
                    lastMsg.role = 'agent';
                    chatMessages = [...chatMessages];
                  }`;

code = code.replace(conversionBlock, `isThinking = false;`);

// Remove error conversion block
const errorConversionBlock = `                  const lastMsg = chatMessages[chatMessages.length - 1];
                  if (lastMsg && lastMsg.role === 'thinking') {
                    lastMsg.text = 'Error: ' + data.text;
                    lastMsg.role = 'agent';
                    chatMessages = [...chatMessages];
                  } else {
                     addMessage('Error: ' + data.text, 'agent');
                  }`;
code = code.replace(errorConversionBlock, `isThinking = false;\n                  addMessage('Error: ' + data.text, 'agent');`);

// And in the AbortError catch:
const abortConversion = `        const lastMsg = chatMessages[chatMessages.length - 1];
        if (lastMsg && lastMsg.role === 'thinking') {
          lastMsg.text = '[Stopped]';
          lastMsg.role = 'agent';
          chatMessages = [...chatMessages];
        }`;
code = code.replace(abortConversion, `isThinking = false;`);


// Chat HTML Generation
const oldChatHistory = `<div id="chat-history" class="flex-grow overflow-y-auto flex flex-col gap-2 p-2 bg-ge-bg rounded-lg border border-ge-border relative neumorphic-inset text-sm">
      {#each chatMessages as msg}
        <div class="p-2 rounded max-w-[90%] whitespace-pre-wrap {msg.role === 'user' ? 'bg-ge-card text-ge-text ml-auto border border-ge-border' : 'bg-transparent text-ge-text-muted mr-auto'}">
          {#if msg.role !== 'user'}
            <div class="text-xs font-bold mb-1 {msg.role === 'thinking' ? 'text-ge-accent/70' : 'text-ge-accent'}">{msg.role === 'thinking' ? 'Thinking...' : 'Z.AI Agent'}</div>
          {/if}
          {msg.text}
        </div>
      {/each}
    </div>`;

const newChatHistory = `<div id="chat-history" class="flex-grow overflow-y-auto flex flex-col gap-2 p-2 bg-ge-bg rounded-lg border border-ge-border relative neumorphic-inset text-sm">
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
                  label={thought}
                  status={i === thoughts.length - 1 && isThinking ? "active" : "complete"}
                />
              {/each}
              {#if isThinking && thoughts.length === 0}
                 <ChainOfThought.Step label="Initializing thought process..." status="active" />
              {/if}
            </ChainOfThought.Content>
          </ChainOfThought.Root>
        </div>
      {/if}
    </div>`;

code = code.replace(oldChatHistory, newChatHistory);

fs.writeFileSync(appPath, code);
