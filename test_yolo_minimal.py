#!/usr/bin/env python3
"""
Minimal test for YOLO achievement - directly uses PyGithub
"""

from github import Github, Auth
import time
from datetime import datetime

# Configuration
TOKEN = 'YOUR_GITHUB_TOKEN_HERE'
REPO_NAME = 'yolo-achievement-test-repo'

def main():
    print("Starting minimal YOLO achievement test...")
    
    # Authenticate
    auth = Auth.Token(TOKEN)
    g = Github(auth=auth)
    
    try:
        user = g.get_user()
        username = user.login
        print(f"Authenticated as: {username}")
    except Exception as e:
        print(f"Authentication failed: {e}")
        return
    
    # Create or get repository
    repo_full_name = f"{username}/{REPO_NAME}"
    try:
        repo = g.get_repo(repo_full_name)
        print(f"Using existing repository: {repo_full_name}")
    except:
        print(f"Creating repository: {REPO_NAME}")
        repo = user.create_repo(
            name=REPO_NAME,
            description="Repository for testing YOLO achievement",
            private=False,
            auto_init=True
        )
        time.sleep(3)  # Wait for repo to be fully created
    
    # Create a branch
    default_branch = repo.default_branch
    base_sha = repo.get_branch(default_branch).commit.sha
    branch_name = f'yolo-achievement-{int(time.time())}'
    
    print(f"Creating branch: {branch_name}")
    repo.create_git_ref(f'refs/heads/{branch_name}', base_sha)
    
    # Create a file
    file_path = f'yolo-{int(time.time())}.txt'
    file_content = f'YOLO achievement test at {datetime.now().isoformat()}'
    
    print(f"Creating file: {file_path}")
    repo.create_file(
        file_path,
        'Add YOLO achievement file',
        file_content,
        branch=branch_name
    )
    
    time.sleep(2)
    
    # Create pull request
    print("Creating pull request...")
    pr = repo.create_pull(
        title='YOLO Achievement PR',
        body='Merging without review for YOLO achievement! 🎯',
        base=default_branch,
        head=branch_name
    )
    
    print(f"Created PR #{pr.number}")
    
    time.sleep(2)
    
    # Merge immediately without review
    print(f"Merging PR #{pr.number} without review...")
    merge_result = pr.merge(
        merge_method='merge',
        commit_title=f'Merge PR #{pr.number}: YOLO Achievement',
        commit_message='Merged without review for YOLO achievement!'
    )
    
    if merge_result.merged:
        print(f"✅ Successfully merged PR #{pr.number} without review!")
        print(f"PR URL: {pr.html_url}")
        print("\nYOLO achievement should be unlocked! Check your GitHub profile.")
    else:
        print("❌ Failed to merge PR")

if __name__ == '__main__':
    main()