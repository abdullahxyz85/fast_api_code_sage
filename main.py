from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import httpx
import os
from dotenv import load_dotenv
import json
import re
from urllib.parse import urlparse
from groq_api import review_pull_request as groq_review_pull_request

load_dotenv()

app = FastAPI(title="GitHub PR Review Agent", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GitHub OAuth configuration
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")

# Pydantic models
class PRReviewRequest(BaseModel):
    pr_url: str
    github_token: Optional[str] = None

class GitHubUser(BaseModel):
    login: str
    id: int
    avatar_url: str
    name: Optional[str] = None
    email: Optional[str] = None

class Repository(BaseModel):
    id: int
    name: str
    full_name: str
    private: bool
    description: Optional[str] = None

class PullRequest(BaseModel):
    id: int
    number: int
    title: str
    state: str
    html_url: str
    created_at: str
    updated_at: str
    user: GitHubUser

class PRReviewResponse(BaseModel):
    summary: str
    issues: List[Dict[str, Any]]
    suggestions: List[str]
    score: Optional[float] = None

# In-memory session storage (in production, use Redis or database)
sessions = {}

def extract_pr_info(pr_url: str) -> tuple:
    """Extract owner, repo, and PR number from GitHub PR URL"""
    # Clean the URL by removing any leading @ symbol and whitespace
    cleaned_url = pr_url.strip().lstrip('@')
    
    # Support multiple URL formats
    patterns = [
        r"github\.com/([^/]+)/([^/]+)/pull/(\d+)",
        r"https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)",
        r"www\.github\.com/([^/]+)/([^/]+)/pull/(\d+)"
    ]
    
    for pattern in patterns:
        match = re.match(pattern, cleaned_url)
        if match:
            return match.group(1), match.group(2), int(match.group(3))
    
    # If no pattern matches, provide a helpful error message
    raise HTTPException(
        status_code=400, 
        detail=f"Invalid GitHub PR URL. Expected format: https://github.com/owner/repo/pull/123. Got: {pr_url}"
    )

async def get_github_user(token: str) -> GitHubUser:
    """Get GitHub user information"""
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"token {token}"}
        response = await client.get("https://api.github.com/user", headers=headers)
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid GitHub token")
        return GitHubUser(**response.json())

@app.get("/")
async def root():
    return {"message": "GitHub PR Review Agent API"}

@app.get("/auth/github")
async def github_login():
    """Initiate GitHub OAuth flow"""
    if not GITHUB_CLIENT_ID:
        raise HTTPException(status_code=500, detail="GitHub OAuth not configured")
    
    # Use the backend callback URL that matches GitHub OAuth app settings
    backend_url = "http://localhost:8000"
    redirect_url = f"https://github.com/login/oauth/authorize?client_id={GITHUB_CLIENT_ID}&scope=repo&redirect_uri={backend_url}/auth/github/callback"
    return {"auth_url": redirect_url}

@app.get("/auth/github/callback")
async def github_callback(code: str):
    """Handle GitHub OAuth callback"""
    if not GITHUB_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="GitHub OAuth not configured")
    
    async with httpx.AsyncClient() as client:
        # Exchange code for access token
        token_response = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code
            },
            headers={"Accept": "application/json"}
        )
        
        if token_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get access token")
        
        token_data = token_response.json()
        if "access_token" not in token_data:
            raise HTTPException(status_code=400, detail="No access token received")
        
        access_token = token_data["access_token"]
        
        # Get user info
        user_response = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"token {access_token}"}
        )
        
        if user_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get user info")
        
        user_data = user_response.json()
        
        # Store session (in production, use secure session management)
        session_id = f"session_{user_data['id']}"
        sessions[session_id] = {
            "access_token": access_token,
            "user": user_data
        }
        
        # Redirect to frontend with session data
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        redirect_url = f"{frontend_url}/login?session_id={session_id}&user={user_data['login']}"
        
        return RedirectResponse(url=redirect_url)

@app.get("/api/user")
async def get_current_user(session_id: str):
    """Get current user information"""
    if session_id not in sessions:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    return sessions[session_id]["user"]

@app.get("/api/user/repos")
async def get_user_repos(session_id: str):
    """Get user's repositories"""
    if session_id not in sessions:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    access_token = sessions[session_id]["access_token"]
    
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"token {access_token}"}
        response = await client.get("https://api.github.com/user/repos", headers=headers)
        
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch repositories")
        
        repos = response.json()
        return [Repository(**repo) for repo in repos]

@app.get("/api/repos/{owner}/{repo}/pulls")
async def get_repo_pulls(owner: str, repo: str, session_id: str):
    """Get pull requests for a repository"""
    if session_id not in sessions:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    access_token = sessions[session_id]["access_token"]
    
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"token {access_token}"}
        response = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/pulls",
            headers=headers
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch pull requests")
        
        pulls = response.json()
        return [PullRequest(**pull) for pull in pulls]

@app.post("/api/review-pr")
async def review_pull_request(request: PRReviewRequest):
    """Review a GitHub pull request using Groq API"""
    
    try:
        owner, repo, pr_number = extract_pr_info(request.pr_url)
    except HTTPException:
        raise HTTPException(status_code=400, detail="Invalid GitHub PR URL")
    
    # Get GitHub access token from session
    headers = {}
    if request.github_token:
        # If session ID is provided, get the actual access token from session
        if request.github_token.startswith("session_"):
            session_id = request.github_token
            print(f"Looking up session: {session_id}")
            if session_id in sessions:
                access_token = sessions[session_id]["access_token"]
                print(f"Found access token for session: {session_id[:10]}...")
                headers["Authorization"] = f"token {access_token}"
            else:
                print(f"Session not found: {session_id}")
                raise HTTPException(status_code=401, detail="Invalid session. Please login again.")
        else:
            # Direct token provided
            print("Using direct token")
            headers["Authorization"] = f"token {request.github_token}"
    else:
        raise HTTPException(status_code=401, detail="GitHub authentication required. Please login first.")
    
    async with httpx.AsyncClient() as client:
        # Get PR details
        pr_response = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}",
            headers=headers
        )
        # print(f"PR Response Status: {pr_response.status_code}")
        # print(f"PR Response: {pr_response.json()}")
        
        if pr_response.status_code == 401:
            raise HTTPException(status_code=401, detail="GitHub authentication failed. Please login again.")
        elif pr_response.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Failed to fetch PR details: {pr_response.json().get('message', 'Unknown error')}")
        
        pr_data = pr_response.json()
        
        # Get PR diff
        diff_response = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}",
            headers={**headers, "Accept": "application/vnd.github.v3.diff"}
        )
        
        if diff_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch PR diff")
        
        diff_content = diff_response.text
        
        # Send to Groq API for review
        review_result = groq_review_pull_request(diff_content)
        
        # Handle potential errors from Groq API
        if isinstance(review_result, str) and review_result.startswith("Error:"):
            raise HTTPException(status_code=500, detail=f"Groq API error: {review_result}")
        
        # Add PR number to the response
        review_result['pr_number'] = pr_number
        
        # Convert Groq response to our expected format
        formatted_result = {
            "summary": review_result.get("review", "Review completed"),
            "issues": review_result.get("errors", []),
            "suggestions": [],  # Groq doesn't provide suggestions in current format
            "score": review_result.get("review_score", 0.0)
        }
        
        return PRReviewResponse(**formatted_result)



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 