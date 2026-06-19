# Zlides V2 (Mongoose Fast Edition)

Zlides V2 is a fully featured, "Mongoose Fast" slide generation engine built on top of the Z.AI GLM-4 model APIs.

## Key Upgrades

1. **Svelte 5 + Tailwind 4 UI**: The entire frontend has been ripped out and replaced with a Mongoose fast Svelte 5 application. It uses a single, smart "vibes" center where prompt detection takes care of everything (rather than cluttering the UI with toggles).
2. **Cost Calculation**: Real-time USD cost estimation directly in the UI. Calculates based on token counts and the Z.AI pricing table, automatically baking in the 2.5x agent overhead multiplier.
3. **Batch Generation**: Write multiple prompts separated by double newlines (`\n\n`), and the UI automatically switches to "Batch Mode". A backend `asyncio.Semaphore` manages the queue to bypass timeouts and rate limits securely.
4. **Smart File & Style Ingestion**: Upload a document or image, and the system hits the GLM File Parser to extract markdown and layout JSON. If you ask for style, it reverse-engineers the uploaded image and dynamically saves it to your `style_bank` without overwriting existing gitEnglish themes!
5. **RR Student Exercises**: Natively supports the RR (RegenResource) format. Generated slides include interactive `<button id="regenerate">` tags that communicate seamlessly with the Svelte UI via iframe `postMessage`.

## Running the App

```bash
# Terminal 1: Build the frontend (if you change it)
cd frontend_svelte
npm run build
rm -rf ../public/assets && cp -r dist/* ../public/

# Terminal 2: Run the server
cd ..
./launch.sh
```
