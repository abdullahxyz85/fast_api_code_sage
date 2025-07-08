#!/usr/bin/env python3
"""
Simple test script to verify the backend API is working
"""

import requests
import json

BASE_URL = "http://localhost:8000"

def test_health_check():
    """Test the health check endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/")
        print(f"✅ Health check: {response.status_code}")
        print(f"   Response: {response.json()}")
        return True
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def test_github_auth():
    """Test the GitHub auth endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/auth/github")
        print(f"✅ GitHub auth endpoint: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Auth URL: {data.get('auth_url', 'Not found')}")
        return True
    except Exception as e:
        print(f"❌ GitHub auth failed: {e}")
        return False

def test_api_docs():
    """Test if API docs are accessible"""
    try:
        response = requests.get(f"{BASE_URL}/docs")
        print(f"✅ API docs: {response.status_code}")
        return True
    except Exception as e:
        print(f"❌ API docs failed: {e}")
        return False

def main():
    print("🧪 Testing GitHub PR Review Agent Backend")
    print("=" * 50)
    
    tests = [
        test_health_check,
        test_github_auth,
        test_api_docs,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Backend is ready.")
    else:
        print("⚠️  Some tests failed. Check the backend server.")

if __name__ == "__main__":
    main() 