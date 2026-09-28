"""Records a high-definition interactive demo video of the Travel Concierge AI agent frontend."""

import asyncio
import os
import shutil
import subprocess
from playwright.async_api import async_playwright

FRONTEND_URL = "https://travel-concierge-frontend-666368138482.us-east1.run.app"
FRAMES_DIR = "frames"
FPS = 15
FRAME_TIME = 1.0 / FPS

async def record_demo():
    if os.path.exists(FRAMES_DIR):
        shutil.rmtree(FRAMES_DIR)
    os.makedirs(FRAMES_DIR, exist_ok=True)

    frame_count = 0

    async def capture_frame(page, count=1):
        nonlocal frame_count
        for _ in range(count):
            filename = os.path.join(FRAMES_DIR, f"frame_{frame_count:04d}.png")
            await page.screenshot(path=filename)
            frame_count += 1
            await asyncio.sleep(FRAME_TIME)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--force-device-scale-factor=1.5"]
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            device_scale_factor=1.5
        )
        page = await context.new_page()

        print("Navigating to Travel Concierge Frontend...")
        await page.goto(FRONTEND_URL, wait_until="networkidle")

        # 1. Initial Welcome Screen (1.5 sec)
        print("Capturing welcome screen...")
        await capture_frame(page, int(1.5 * FPS))

        # 2. Click Chip: "All Destinations"
        print("Clicking 'All Destinations' chip...")
        all_dest_chip = page.locator('.chip:has-text("All Destinations")')
        if await all_dest_chip.count() > 0:
            await all_dest_chip.click()
            # Capture typing indicator & catalog response (4.5 sec)
            for _ in range(int(4.5 * FPS)):
                await capture_frame(page, 1)

        # 3. Type prompt 2: "Calculate a 5 day trip budget for Kyoto for 2 travelers"
        print("Typing Kyoto budget calculation prompt...")
        input_el = page.locator("#input")
        await input_el.focus()
        prompt_text = "Calculate a 5 day trip budget for Kyoto for 2 travelers"
        for char in prompt_text:
            await input_el.type(char, delay=35)
            await capture_frame(page, 1)

        await page.keyboard.press("Enter")
        print("Sent budget request. Waiting for response...")
        for _ in range(int(5.0 * FPS)):
            await capture_frame(page, 1)

        # 4. Click Chip: "Generate Bali image" or type image prompt
        print("Typing Bali image generation prompt...")
        await input_el.focus()
        img_prompt = "Generate an image of a serene beach in Bali"
        for char in img_prompt:
            await input_el.type(char, delay=35)
            await capture_frame(page, 1)

        await page.keyboard.press("Enter")
        print("Sent image request. Waiting for generated image...")
        for _ in range(int(8.0 * FPS)):
            await capture_frame(page, 1)

        # 5. Click on the generated image to activate Lightbox modal preview
        print("Opening Lightbox preview modal...")
        images = page.locator(".chat-image, .a2img")
        if await images.count() > 0:
            await images.last.click()
            await capture_frame(page, int(2.5 * FPS))

            # Close modal
            close_btn = page.locator("#modal-close")
            if await close_btn.count() > 0:
                await close_btn.click()
                await capture_frame(page, int(1.0 * FPS))

        # 6. Toggle Dark Mode
        print("Toggling Dark Mode...")
        theme_btn = page.locator("#theme-toggle")
        if await theme_btn.count() > 0:
            await theme_btn.click()
            await capture_frame(page, int(2.5 * FPS))

        # 7. Start New Session
        print("Resetting session...")
        new_chat_btn = page.locator("#new-chat-btn")
        if await new_chat_btn.count() > 0:
            await new_chat_btn.click()
            await capture_frame(page, int(2.0 * FPS))

        await browser.close()

    print(f"Captured total {frame_count} frames.")

    # 8. Compile video with ffmpeg and lo-fi audio track
    print("Compiling demo_video.mp4 with ffmpeg and lo-fi background music...")
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", "frames/frame_%04d.png",
        "-i", "lofi_track.wav",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-shortest",
        "demo_video.mp4"
    ]
    subprocess.run(cmd, check=True)
    print("Successfully produced demo_video.mp4!")

if __name__ == "__main__":
    asyncio.run(record_demo())
