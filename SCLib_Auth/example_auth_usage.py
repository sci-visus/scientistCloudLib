#!/usr/bin/env python3
"""
SCLib Authentication System - Example Usage
Demonstrates how to use the standalone authentication system.
"""

import requests
import json
import time
from typing import Dict, Any

class SCLibAuthClient:
    """Client for interacting with the SCLib Authentication API."""
    
    def __init__(self, base_url: str = "http://localhost:8001"):
        """
        Initialize the authentication client.
        
        Args:
            base_url: Base URL of the authentication server
        """
        self.base_url = base_url.rstrip('/')
        self.access_token = None
        self.refresh_token = None
        self.user_info = None
    
    def login(self, email: str, password: str = None) -> Dict[str, Any]:
        """
        Login with email and optional password.
        
        Args:
            email: User's email address
            password: Optional password
            
        Returns:
            Login response data
        """
        url = f"{self.base_url}/api/auth/login"
        payload = {
            "email": email,
            "password": password
        }
        
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            if data.get('success'):
                self.access_token = data['data']['access_token']
                self.refresh_token = data['data']['refresh_token']
                self.user_info = data['data']['user']
                print(f"✅ Login successful for {email}")
                return data
            else:
                print(f"❌ Login failed: {data.get('message', 'Unknown error')}")
                return data
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Login request failed: {e}")
            return {"success": False, "error": str(e)}
    
    def get_user_info(self) -> Dict[str, Any]:
        """
        Get current user information.
        
        Returns:
            User information
        """
        if not self.access_token:
            print("❌ No access token available. Please login first.")
            return {"success": False, "error": "No access token"}
        
        url = f"{self.base_url}/api/auth/me"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            print(f"✅ User info retrieved for {data.get('email', 'unknown')}")
            return data
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Get user info failed: {e}")
            return {"error": str(e)}
    
    def refresh_access_token(self) -> Dict[str, Any]:
        """
        Refresh the access token using refresh token.
        
        Returns:
            New token data
        """
        if not self.refresh_token:
            print("❌ No refresh token available. Please login first.")
            return {"success": False, "error": "No refresh token"}
        
        url = f"{self.base_url}/api/auth/refresh"
        payload = {"refresh_token": self.refresh_token}
        
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            if data.get('success'):
                self.access_token = data['data']['access_token']
                self.refresh_token = data['data']['refresh_token']
                print("✅ Access token refreshed successfully")
                return data
            else:
                print(f"❌ Token refresh failed: {data.get('message', 'Unknown error')}")
                return data
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Token refresh request failed: {e}")
            return {"success": False, "error": str(e)}
    
    def logout(self) -> Dict[str, Any]:
        """
        Logout and revoke tokens.
        
        Returns:
            Logout response
        """
        if not self.access_token:
            print("❌ No access token available. Already logged out.")
            return {"success": False, "error": "No access token"}
        
        url = f"{self.base_url}/api/auth/logout"
        payload = {"token": self.access_token}
        
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            if data.get('success'):
                self.access_token = None
                self.refresh_token = None
                self.user_info = None
                print("✅ Logout successful")
                return data
            else:
                print(f"❌ Logout failed: {data.get('message', 'Unknown error')}")
                return data
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Logout request failed: {e}")
            return {"success": False, "error": str(e)}
    
    def check_auth_status(self) -> Dict[str, Any]:
        """
        Check authentication status.
        
        Returns:
            Authentication status
        """
        url = f"{self.base_url}/api/auth/status"
        headers = {}
        
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            status = "authenticated" if data.get('is_authenticated') else "not authenticated"
            print(f"🔍 Auth status: {status}")
            return data
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Auth status check failed: {e}")
            return {"error": str(e)}
    
    def get_server_info(self) -> Dict[str, Any]:
        """
        Get server information and available endpoints.
        
        Returns:
            Server information
        """
        url = f"{self.base_url}/"
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            
            data = response.json()
            print(f"🌐 Connected to {data.get('message', 'Unknown server')}")
            return data
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Server info request failed: {e}")
            return {"error": str(e)}

def main():
    """Main function demonstrating authentication system usage."""
    print("🚀 SCLib Authentication System - Example Usage")
    print("=" * 50)
    
    # Initialize client
    client = SCLibAuthClient()
    
    # Check server connection
    print("\n1. Checking server connection...")
    server_info = client.get_server_info()
    if "error" in server_info:
        print("❌ Cannot connect to authentication server. Make sure it's running on http://localhost:8001")
        return
    
    # Check initial auth status
    print("\n2. Checking initial authentication status...")
    client.check_auth_status()
    
    # Login
    print("\n3. Logging in...")
    email = "test@example.com"
    login_result = client.login(email)
    
    if not login_result.get('success'):
        print("❌ Login failed. Please check your authentication server configuration.")
        return
    
    # Get user info
    print("\n4. Getting user information...")
    user_info = client.get_user_info()
    if "error" not in user_info:
        print(f"   User ID: {user_info.get('user_id')}")
        print(f"   Email: {user_info.get('email')}")
        print(f"   Name: {user_info.get('name')}")
        print(f"   Email Verified: {user_info.get('email_verified')}")
    
    # Check auth status after login
    print("\n5. Checking authentication status after login...")
    client.check_auth_status()
    
    # Refresh token
    print("\n6. Refreshing access token...")
    refresh_result = client.refresh_access_token()
    if refresh_result.get('success'):
        print("   ✅ Token refreshed successfully")
    else:
        print("   ❌ Token refresh failed")
    
    # Wait a moment
    print("\n7. Waiting 2 seconds...")
    time.sleep(2)
    
    # Logout
    print("\n8. Logging out...")
    logout_result = client.logout()
    if logout_result.get('success'):
        print("   ✅ Logout successful")
    else:
        print("   ❌ Logout failed")
    
    # Check auth status after logout
    print("\n9. Checking authentication status after logout...")
    client.check_auth_status()
    
    print("\n🎉 Authentication system demonstration complete!")
    print("\nTo run your own authentication server:")
    print("   cd /path/to/SCLib_Auth")
    print("   python start_auth_server.py --port 8001")

if __name__ == "__main__":
    main()




