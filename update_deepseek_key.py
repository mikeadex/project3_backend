#!/usr/bin/env python
"""
A utility script to update the DeepSeek API key in your .env file
or create a new one if it doesn't exist.
"""

import os
import sys
from pathlib import Path
import re

def update_env_file(new_key):
    """Update the DeepSeek API key in the .env file"""
    env_path = Path('.env')
    
    # Check if .env file exists
    if env_path.exists():
        with open(env_path, 'r') as file:
            content = file.read()
        
        # Check if DEEPSEEK_API_KEY already exists in the file
        if re.search(r'^DEEPSEEK_API_KEY=', content, re.MULTILINE):
            # Replace existing key
            updated_content = re.sub(
                r'^DEEPSEEK_API_KEY=.*$', 
                f'DEEPSEEK_API_KEY={new_key}', 
                content, 
                flags=re.MULTILINE
            )
        else:
            # Add key to the end of the file
            updated_content = content
            if not updated_content.endswith('\n'):
                updated_content += '\n'
            updated_content += f'DEEPSEEK_API_KEY={new_key}\n'
        
        # Write the updated content back to the file
        with open(env_path, 'w') as file:
            file.write(updated_content)
        print(f"✅ Updated DEEPSEEK_API_KEY in .env file")
    else:
        # Create new .env file with the key
        with open(env_path, 'w') as file:
            file.write(f'DEEPSEEK_API_KEY={new_key}\n')
        print(f"✅ Created new .env file with DEEPSEEK_API_KEY")
    
    print("\nTo apply this change, restart your Django server")
    print("Remember to keep your API key secure and never commit it to version control")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python update_deepseek_key.py YOUR_API_KEY")
        sys.exit(1)
    
    api_key = sys.argv[1]
    update_env_file(api_key)
