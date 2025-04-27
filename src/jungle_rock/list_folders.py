#!/usr/bin/env python3
"""
List available mailboxes/folders in ProtonMail Bridge
"""

import imaplib
import configparser
import os

def load_config(config_file='config.ini'):
    """Load configuration from the specified file."""
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Config file not found: {config_file}")
    
    config = configparser.ConfigParser()
    config.read(config_file)
    return config

def list_folders(config_file='config.ini'):
    """List all available folders in the ProtonMail account."""
    
    # Load configuration
    config = load_config(config_file)
    
    # Connect to IMAP server
    try:
        # Connect to the IMAP server provided by ProtonMail Bridge
        conn = imaplib.IMAP4(
            host=config['ProtonMail']['imap_server'],
            port=int(config['ProtonMail']['imap_port'])
        )
        
        # Login using your ProtonMail email and Bridge password
        conn.login(
            config['ProtonMail']['email'], 
            config['ProtonMail']['bridge_password']
        )
        
        print("Successfully connected to ProtonMail Bridge")
        
        # List all available mailboxes/folders
        status, folder_list = conn.list()
        
        if status != 'OK':
            print(f"Failed to get folder list: {folder_list}")
            return
        
        print("\nAvailable folders:")
        print("-------------------")
        
        for folder in folder_list:
            decoded_folder = folder.decode('utf-8')
            # Clean up the folder name for easier reading
            try:
                # Extract folder name from response (format typically: '(flags) delimiter "folder_name"')
                folder_name = decoded_folder.split('"')[-2]
                print(f"- {folder_name}")
            except:
                # If parsing fails, show the raw entry
                print(f"- {decoded_folder}")
        
        print("\nTo use a specific folder, update your config.ini:")
        print('mailbox = folder_name')
        
        # Close the connection
        conn.logout()
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    import sys
    config_file = 'config.ini'
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
    
    list_folders(config_file)