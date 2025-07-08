#!/usr/bin/env python3
"""
Manual webhook cleaner for Telegram bot
Run this to force clear any existing webhook
"""
import os
import sys
import requests
import json

def clear_webhook():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        print("❌ TELEGRAM_BOT_TOKEN environment variable not set!")
        return False
        
    print(f"🔍 Clearing webhook for bot: {token[:10]}...{token[-4:]}")
    
    # Check current webhook status
    webhook_info_url = f"https://api.telegram.org/bot{token}/getWebhookInfo"
    try:
        response = requests.get(webhook_info_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('ok'):
                webhook_info = data['result']
                webhook_url = webhook_info.get('url', '')
                pending_updates = webhook_info.get('pending_update_count', 0)
                
                print(f"📋 Current webhook info:")
                print(f"   URL: {webhook_url or 'Not set'}")
                print(f"   Pending updates: {pending_updates}")
                print(f"   Last error: {webhook_info.get('last_error_message', 'None')}")
                
                if webhook_url:
                    print("⚠️  Found active webhook! Deleting...")
                else:
                    print("✅ No webhook found")
                    return True
            else:
                print(f"❌ API error: {data}")
                return False
        else:
            print(f"❌ HTTP error: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error checking webhook: {e}")
        return False
    
    # Force delete webhook
    delete_url = f"https://api.telegram.org/bot{token}/deleteWebhook"
    try:
        # Try with drop_pending_updates=true to be more aggressive
        delete_response = requests.post(delete_url, 
                                      json={"drop_pending_updates": True}, 
                                      timeout=10)
        
        if delete_response.status_code == 200:
            delete_data = delete_response.json()
            if delete_data.get('ok'):
                print("✅ Webhook deleted successfully!")
                
                # Verify deletion
                verify_response = requests.get(webhook_info_url, timeout=10)
                if verify_response.status_code == 200:
                    verify_data = verify_response.json()
                    if verify_data.get('ok'):
                        new_url = verify_data['result'].get('url', '')
                        if not new_url:
                            print("✅ Webhook deletion verified!")
                            return True
                        else:
                            print(f"❌ Webhook still active: {new_url}")
                            return False
                
                return True
            else:
                print(f"❌ Failed to delete webhook: {delete_data}")
                return False
        else:
            print(f"❌ HTTP error deleting webhook: {delete_response.status_code}")
            print(f"Response: {delete_response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error deleting webhook: {e}")
        return False

if __name__ == "__main__":
    print("🧹 Manual Webhook Cleaner")
    print("=" * 30)
    
    success = clear_webhook()
    
    if success:
        print("\n🎉 Webhook cleared successfully!")
        print("Your bot should now be able to use polling mode.")
    else:
        print("\n❌ Failed to clear webhook.")
        print("You may need to check your bot token or try again later.")
    
    sys.exit(0 if success else 1)