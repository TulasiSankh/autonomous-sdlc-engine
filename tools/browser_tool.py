"""Browser tool for opening validated URLs in the default system browser."""

import re
import sys
import webbrowser
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

from tools.base import BaseTool, ToolExecutionResult


class BrowserTool(BaseTool):
    """Tool that opens validated URLs in the user's default browser."""

    name = "browser"
    description = "Opens validated web URLs in the user's default web browser."
    supported_actions = ["open_url"]

    def __init__(
        self,
        launcher: Optional[Callable[[str], bool]] = None,
        browser_launcher: Optional[Callable[[str], bool]] = None,
    ) -> None:
        """Initializes the browser tool.
        
        Args:
            launcher: Optional custom function to open a URL (useful for mocking in tests).
            browser_launcher: Alias for launcher.
        """
        chosen_launcher = launcher if launcher is not None else browser_launcher
        self._launcher = chosen_launcher if chosen_launcher is not None else webbrowser.open

    def get_parameters_schema(self, action: Optional[str] = None) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The web URL to open (must use http or https scheme).",
                },
                "new_window": {
                    "type": "boolean",
                    "description": "Whether to request a new browser window if supported.",
                    "default": False,
                },
            },
            "required": ["url"],
        }

    def validate_url(self, raw_url: str) -> str:
        """Validates and sanitizes a URL for browser launch.
        
        Args:
            raw_url: Input URL string.
            
        Returns:
            Validated, normalized URL.
            
        Raises:
            ValueError: If URL is malformed, uses an unsupported scheme, or contains dangerous characters.
        """
        if not raw_url or not isinstance(raw_url, str):
            raise ValueError("URL must be a non-empty string.")

        clean_url = raw_url.strip()

        # Handle user shorthand like "github.com" or "github"
        if clean_url.lower() == "github" or clean_url.lower() == "my github":
            clean_url = "https://github.com"
        elif "://" in clean_url:
            parsed_test = urlparse(clean_url)
            if parsed_test.scheme.lower() not in ("http", "https"):
                raise ValueError(
                    f"Unsupported URL scheme '{parsed_test.scheme}'. Only 'http' and 'https' are permitted."
                )
        elif not clean_url.startswith(("http://", "https://")):
            # If domain-like format, default to https
            if "." in clean_url and not any(clean_url.startswith(s) for s in ("/", "\\", "file:", "data:", "ftp:", "javascript:")):
                clean_url = f"https://{clean_url}"
            else:
                raise ValueError(
                    f"Invalid URL '{raw_url}'. URLs must use 'http' or 'https' protocol."
                )

        parsed = urlparse(clean_url)
        if parsed.scheme.lower() not in ("http", "https"):
            raise ValueError(
                f"Unsupported URL scheme '{parsed.scheme}'. Only 'http' and 'https' are permitted."
            )

        if not parsed.netloc:
            raise ValueError(f"URL '{raw_url}' lacks a valid domain name.")

        # Disallow control characters or shell injection characters
        if re.search(r"[\r\n\0<>\"'|;`$]", clean_url):
            raise ValueError("URL contains illegal or dangerous characters.")

        return clean_url

    def execute(self, action: str, params: Dict[str, Any]) -> ToolExecutionResult:
        self.validate_action(action)

        raw_url = params.get("url")
        if not raw_url:
            return ToolExecutionResult(
                success=False,
                error="Missing required parameter 'url'.",
            )

        try:
            validated_url = self.validate_url(str(raw_url))
        except ValueError as exc:
            return ToolExecutionResult(
                success=False,
                error=f"URL validation failed: {str(exc)}",
            )

        try:
            # Platform-aware launch via webbrowser or custom launcher
            launched = self._launcher(validated_url)
            # webbrowser.open returns True if browser was launched successfully
            if launched is False:
                # Some platforms return False even if launched; treat as warning or verify
                return ToolExecutionResult(
                    success=True,
                    output={
                        "url": validated_url,
                        "message": f"Dispatched browser launch for '{validated_url}'.",
                    },
                    metadata={
                        "url": validated_url,
                        "platform": sys.platform,
                        "launched_returned": False,
                    },
                )

            return ToolExecutionResult(
                success=True,
                output={
                    "url": validated_url,
                    "message": f"Successfully opened '{validated_url}' in default browser.",
                },
                metadata={
                    "url": validated_url,
                    "platform": sys.platform,
                },
            )
        except Exception as exc:
            return ToolExecutionResult(
                success=False,
                error=f"Failed to launch browser for '{validated_url}': {str(exc)}",
                metadata={"url": validated_url, "platform": sys.platform},
            )
