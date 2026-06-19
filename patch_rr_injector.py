import sys

filename = "slide_server.py"
with open(filename, "r") as f:
    content = f.read()

injector_code = """
import re

class StudentExerciseInjector:
    \"\"\"Injects JS required for the RR (RegenResource) format to work properly.\"\"\"
    def inject(self, html: str) -> str:
        # If it doesn't have the regenerate button, ignore
        if "id='regenerate'" not in html and 'id="regenerate"' not in html:
            return html

        script = \"\"\"
        <script>
        // Student exercise regeneration system (RR format)
        document.querySelectorAll('button[id=\"regenerate\"]').forEach(btn => {
            btn.addEventListener('click', async function() {
                const prompt = this.getAttribute('data-prompt') || 'Regenerate this section';
                this.innerHTML = 'Regenerating...';
                this.disabled = true;

                try {
                    // Send message to parent Svelte app to trigger the API
                    window.parent.postMessage({ type: 'regenerate', prompt: prompt }, '*');
                } catch(e) {
                    this.innerHTML = 'Error';
                }
            });
        });

        window.addEventListener('message', (event) => {
            if (event.data.type === 'regenerate_done') {
                // We would replace the DOM here based on the result
                console.log("Regeneration completed");
            }
        });
        </script>
        \"\"\"
        if "</body>" in html:
            return html.replace("</body>", f"{script}</body>")
        return html + script

exercise_injector = StudentExerciseInjector()

# Hook into the export/save logic
def save_slide_to_file(html: str, prompt: str) -> str:
    html = exercise_injector.inject(html)
"""

content = content.replace("def save_slide_to_file(html: str, prompt: str) -> str:", injector_code + "\n    ")

with open(filename, "w") as f:
    f.write(content)
