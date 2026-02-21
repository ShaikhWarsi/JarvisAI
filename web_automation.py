import asyncio
from playwright.async_api import async_playwright
import logging

# Global WebAutomator instance
_automator = None

class WebAutomator:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self._is_initialized = False

    async def ensure_initialized(self):
        if not self._is_initialized:
            try:
                self.playwright = await async_playwright().start()
                # Launch headed so the user can see it (Visualized)
                self.browser = await self.playwright.chromium.launch(headless=False, slow_mo=1000) # Slower for demo effect
                self.context = await self.browser.new_context()
                self.page = await self.context.new_page()
                self._is_initialized = True
                print("WebAutomator initialized (Headless: False).")
            except Exception as e:
                print(f"Failed to initialize WebAutomator: {e}")
                raise e

    async def stop(self):
        if self._is_initialized:
            await self.context.close()
            await self.browser.close()
            await self.playwright.stop()
            self._is_initialized = False
            print("WebAutomator stopped.")

    async def browse(self, url: str):
        await self.ensure_initialized()
        try:
            print(f"Navigating to: {url}")
            await self.page.goto(url)
            title = await self.page.title()
            return f"Navigated to '{title}'. You can now use web_click or web_type."
        except Exception as e:
            return f"Error navigating to {url}: {e}"

    async def click(self, selector: str):
        if not self._is_initialized:
            return "Error: Browser not active. Use browse_web(url) first."
        try:
            # Wait for element to be visible
            await self.page.wait_for_selector(selector, timeout=5000)
            await self.page.click(selector)
            return f"Clicked element: {selector}"
        except Exception as e:
            return f"Error clicking {selector}: {e}"

    async def type_text(self, selector: str, text: str):
        if not self._is_initialized:
             return "Error: Browser not active. Use browse_web(url) first."
        try:
            await self.page.wait_for_selector(selector, timeout=5000)
            await self.page.fill(selector, text)
            return f"Typed '{text}' into {selector}"
        except Exception as e:
            return f"Error typing into {selector}: {e}"
            
    async def get_content(self):
        if not self._is_initialized:
             return "Error: Browser not active."
        try:
            content = await self.page.inner_text("body")
            return content[:4000] # Return reasonable amount of text
        except Exception as e:
            return f"Error getting content: {e}"

# Singleton management
def get_automator():
    global _automator
    if _automator is None:
        _automator = WebAutomator()
    return _automator

# --- Exported Functions for AI Tools ---

async def browse_web(url: str):
    """Opens a website using a real browser (Playwright). reliable for dynamic sites.
    Args:
        url: The URL to visit (e.g., 'https://www.google.com').
    """
    automator = get_automator()
    return await automator.browse(url)

async def web_click(selector: str):
    """Clicks an element on the current web page using a CSS selector.
    Args:
        selector: The CSS selector (e.g., '#search-button', '.nav-link').
    """
    automator = get_automator()
    return await automator.click(selector)

async def web_type(selector: str, text: str):
    """Types text into an input field on the current web page.
    Args:
        selector: The CSS selector for the input (e.g., 'input[name="q"]').
        text: The text to type.
    """
    automator = get_automator()
    return await automator.type_text(selector, text)

async def web_read():
    """Reads the text content of the current web page."""
    automator = get_automator()
    return await automator.get_content()

async def close_browser():
    """Closes the web browser."""
    automator = get_automator()
    await automator.stop()
    return "Browser closed."
