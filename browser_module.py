"""
Phase 2: Headless Browser Module
Visits quiz URLs, executes JavaScript, and extracts quiz content
"""

import asyncio
import base64
import re
from typing import Dict, Optional

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

class QuizBrowser:
    """Handles browser automation for quiz pages"""
    
    def __init__(self, headless: bool = True):
        """
        Initialize browser
        Args:
            headless: Run browser in headless mode (no visible window)
        """
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
    
    async def start(self):
        """Start the browser"""
        print("🌐 Starting browser...")
        if self.playwright:
            print("⚠ Browser already running")
            return
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        self.page = await self.context.new_page()
        print("✓ Browser started")
    
    async def stop(self):
        """Clean up browser resources"""
        if self.page:
            await self.page.close()
            self.page = None
        if self.context:
            await self.context.close()
            self.context = None
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
        print("✓ Browser stopped")
    
    async def visit_quiz_page(self, url: str, timeout: int = 30000) -> Dict:
        """
        Visit a quiz URL and extract the quiz content
        
        Args:
            url: The quiz page URL
            timeout: Page load timeout in milliseconds
            
        Returns:
            Dict with quiz_text, submit_url, and raw_html
        """
        print(f"📄 Visiting: {url}")
        
        try:
            # Navigate to the page
            response = await self.page.goto(url, wait_until="networkidle", timeout=timeout)
            
            if not response or response.status != 200:
                return {
                    "error": f"Failed to load page. Status: {response.status if response else 'No response'}",
                    "url": url
                }
            
            # Wait for any dynamic content to load
            await self.page.wait_for_timeout(2000)  # 2 second wait for JS execution
            
            # Get the rendered HTML content
            html_content = await self.page.content()
            
            # Try to extract quiz text from common elements
            quiz_text = await self._extract_quiz_content(html_content)
            
            # Try to extract submission URL
            submit_url = self._extract_submit_url(quiz_text)
            
            print(f"✓ Page loaded successfully")
            print(f"📝 Quiz content length: {len(quiz_text)} chars")
            if submit_url:
                print(f"🎯 Submit URL found: {submit_url}")
            
            return {
                "success": True,
                "url": url,
                "quiz_text": quiz_text,
                "submit_url": submit_url,
                "raw_html": html_content
            }
            
        except PlaywrightTimeout:
            return {
                "error": "Page load timeout",
                "url": url
            }
        except Exception as e:
            return {
                "error": f"Browser error: {str(e)}",
                "url": url
            }
    
    async def _extract_quiz_content(self, html: str) -> str:
        """
        Extract and decode quiz content from HTML
        Handles base64 encoded content in script tags
        """
        # Try to find base64 encoded content in script tags
        base64_pattern = r'atob\([`"\']([A-Za-z0-9+/=]+)[`"\']\)'
        matches = re.findall(base64_pattern, html)
        
        decoded_parts = []
        for encoded in matches:
            try:
                decoded = base64.b64decode(encoded).decode('utf-8')
                decoded_parts.append(decoded)
            except Exception as e:
                print(f"⚠ Failed to decode base64: {e}")
        
        # If we found decoded content, use it
        if decoded_parts:
            return '\n\n'.join(decoded_parts)
        
        # Otherwise, try to get text from result div or body
        try:
            if self.page:
                # Try common quiz content selectors
                selectors = ['#result', '#quiz', '#content', '.quiz-content', 'body']
                for selector in selectors:
                    try:
                        text = await self.page.text_content(selector, timeout=1000)
                        if text and len(text.strip()) > 50:  # Meaningful content
                            return text.strip()
                    except Exception:
                        continue
        except Exception as e:
            print(f"⚠ Error extracting text: {e}")
        
        # Fallback: return cleaned HTML
        return self._clean_html(html)
    
    def _clean_html(self, html: str) -> str:
        """Remove script and style tags from HTML"""
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<[^>]+>', ' ', html)
        html = re.sub(r'\s+', ' ', html)
        return html.strip()
    
    def _extract_submit_url(self, text: str) -> Optional[str]:
        """
        Extract the submission URL from quiz text
        Looks for patterns like: "Post your answer to https://..."
        """
        # Pattern to find URLs in text
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+/submit[^\s<>"{}|\\^`\[\]]*'
        matches = re.findall(url_pattern, text)
        
        if matches:
            return matches[0]
        
        # Broader pattern if specific submit URL not found
        url_pattern_broad = r'Post.*?to\s+(https?://[^\s<>"{}|\\^`\[\]]+)'
        matches = re.findall(url_pattern_broad, text, re.IGNORECASE)
        
        if matches:
            return matches[0]
        
        return None


# Test function
async def test_browser():
    """Test the browser with the demo endpoint"""
    browser = QuizBrowser(headless=False)  # Set to True for headless mode
    
    try:
        await browser.start()
        
        # Test with demo URL
        test_url = "https://tds-llm-analysis.s-anand.net/demo"
        result = await browser.visit_quiz_page(test_url)
        
        if "error" in result:
            print(f"❌ Error: {result['error']}")
        else:
            print("\n" + "="*60)
            print("QUIZ CONTENT:")
            print("="*60)
            print(result['quiz_text'][:500])  # First 500 chars
            print("\n" + "="*60)
            print(f"Submit URL: {result['submit_url']}")
            print("="*60)
        
    finally:
        await browser.stop()


if __name__ == "__main__":
    # Install required package first:
    # pip install playwright
    # playwright install chromium
    
    print("Phase 2: Browser Module Test\n")
    asyncio.run(test_browser())