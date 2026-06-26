const fs = require('fs');

const appPath = 'frontend_svelte/src/App.svelte';
let code = fs.readFileSync(appPath, 'utf-8');

// I need to add state for citations
const stateAddition = `
  let toolCalls: { name: string, input: string }[] = [];
  let currentToolBuffer = '';
  let currentToolName = '';
`;
code = code.replace("let thoughts: string[] = [];", "let thoughts: string[] = [];\n" + stateAddition);

// Update generate to clear tools
code = code.replace("thoughts = [];", "thoughts = [];\n    toolCalls = [];\n    currentToolBuffer = '';\n    currentToolName = '';");

// Find the thinking loop and parse tool events out if possible
const toolParserBlock = `                if (data.type === 'tool') {
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
                }`;

// Insert tool parser right before the answer block
code = code.replace("if (data.type === 'answer') {", toolParserBlock + "\n\n                if (data.type === 'answer') {");

// Now update the ChainOfThought markup to include SearchResults if toolCalls exist
const searchResultsMarkup = `
              {#if toolCalls.length > 0}
                <ChainOfThought.SearchResults class="mt-2">
                  {#each toolCalls as call}
                    <ChainOfThought.SearchResult>{call.name}: {call.input.length > 20 ? call.input.substring(0,20)+'...' : call.input}</ChainOfThought.SearchResult>
                  {/each}
                </ChainOfThought.SearchResults>
              {/if}
              {#if isThinking && thoughts.length === 0}
`;

code = code.replace("{#if isThinking && thoughts.length === 0}", searchResultsMarkup);

// Also look for markdown image links in thoughts and convert them to ChainOfThought.Image
// Since we don't have a specific event for images, we can regex the thoughts for markdown images `![alt](url)`
// I'll add a helper function to extract them
const extractImagesScript = `
  function extractImages(thought: string) {
    const images = [];
    const regex = /!\\[(.*?)\\]\\((.*?)\\)/g;
    let match;
    while ((match = regex.exec(thought)) !== null) {
      images.push({ alt: match[1], url: match[2] });
    }
    return images;
  }

  function stripImages(thought: string) {
    return thought.replace(/!\\[(.*?)\\]\\((.*?)\\)/g, '').trim();
  }
`;
code = code.replace("function renderLiveHtmlChunks() {", extractImagesScript + "\n\n  function renderLiveHtmlChunks() {");

const stepMarkupOld = `<ChainOfThought.Step
                  label={thought}
                  status={i === thoughts.length - 1 && isThinking ? "active" : "complete"}
                />`;
const stepMarkupNew = `<ChainOfThought.Step
                  label={stripImages(thought) || "Looking at image..."}
                  status={i === thoughts.length - 1 && isThinking ? "active" : "complete"}
                >
                  {#each extractImages(thought) as img}
                    <ChainOfThought.Image caption={img.alt}>
                      <img src={img.url} alt={img.alt} class="w-full h-auto rounded" />
                    </ChainOfThought.Image>
                  {/each}
                </ChainOfThought.Step>`;

code = code.replace(stepMarkupOld, stepMarkupNew);

fs.writeFileSync(appPath, code);
