#!/usr/bin/env python3
"""Generate service configurations from BotSpec."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from qiki.shared.config.generator import generate_bot_config_from_spec, save_bot_config


def main():
    """Generate configurations for all services."""
    # Generate bot config
    bot_config = generate_bot_config_from_spec()
    
    # Save to q_core_agent config
    save_bot_config(
        bot_config, 
        Path(__file__).parent / "qiki" / "services" / "q_core_agent" / "config" / "bot_config.json"
    )
    
    print("Configuration files generated successfully!")


if __name__ == "__main__":
    main()