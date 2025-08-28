"""
Reusable browser configuration for persistent profiles.
Import this in any script to use the same persistent browser profile.
"""

from browser_use import BrowserSession, BrowserProfile
from pathlib import Path

def get_persistent_browser_session():
    """
    Returns a BrowserSession configured with the persistent profile.
    Use this in any script to ensure extensions and settings persist.
    """
    # Create persistent browser profile
    user_data_dir = Path.home() / ".config" / "browseruse" / "profiles" / "persistent"
    user_data_dir.mkdir(parents=True, exist_ok=True)
    
    browser_profile = BrowserProfile(
        headless=False,  # Keep browser visible
        user_data_dir=str(user_data_dir),
        keep_alive=True,  # Keep browser open after agent completes
        viewport={"width": 1280, "height": 800},
    )
    
    return BrowserSession(browser_profile=browser_profile)

def get_persistent_browser_profile():
    """
    Returns just the BrowserProfile for custom configuration.
    """
    user_data_dir = Path.home() / ".config" / "browseruse" / "profiles" / "persistent"
    user_data_dir.mkdir(parents=True, exist_ok=True)
    
    return BrowserProfile(
        headless=False,
        user_data_dir=str(user_data_dir),
        keep_alive=True,
        viewport={"width": 1280, "height": 800},
    )
