#!/usr/bin/env python3
"""
Create repo and test YOLO achievement with pending review
"""

from github import Github, Auth
import time
from datetime import datetime

# Configuration
TOKEN = 'YOUR_GITHUB_TOKEN_HERE'
REPO_NAME = 'yolo-achievement-test-repo'

def main():
    print("Creating repository and testing YOLO achievement...")
    
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
    branch_name = f'yolo-review-{int(time.time())}'
    
    print(f"Creating branch: {branch_name}")
    repo.create_git_ref(f'refs/heads/{branch_name}', base_sha)
    
    # Create a file
    file_path = f'yolo-review-{int(time.time())}.txt'
    file_content = f'YOLO achievement with review test at {datetime.now().isoformat()}'
    
    print(f"Creating file: {file_path}")
    repo.create_file(
        file_path,
        'Add YOLO achievement file for review',
        file_content,
        branch=branch_name
    )
    
    time.sleep(2)
    
    # Create pull request
    print("Creating pull request...")
    pr = repo.create_pull(
        title='YOLO Achievement PR - Testing Pending Review',
        body='This PR will be merged with a pending review for the YOLO achievement! 🎯',
        base=default_branch,
        head=branch_name
    )
    
    print(f"Created PR #{pr.number}")
    print(f"PR URL: {pr.html_url}")
    
    # Try to request a review from yourself (won't work but shows the concept)
    print("\nNote: To properly get the YOLO achievement, you need:")
    print("1. Have someone else as a collaborator who can review")
    print("2. Request a review from them")
    print("3. Merge the PR while the review is still pending")
    print("\nSince we can't request review from ourselves, you'll need to:")
    print(f"1. Add a collaborator to the repo: https://github.com/{username}/{REPO_NAME}/settings/access")
    print("2. Request their review on the PR")
    print("3. Merge before they complete the review")
    
    # Try merging anyway to show it works without review too
    time.sleep(2)
    print(f"\nMerging PR #{pr.number}...")
    try:
        merge_result = pr.merge(
            merge_method='merge',
            commit_title=f'Merge PR #{pr.number}: YOLO Test',
            commit_message='Testing YOLO achievement process'
        )
        
        if merge_result.merged:
            print(f"✅ PR merged successfully!")
            print("\nHowever, this won't unlock YOLO since no review was pending.")
            print("You need to have a pending review when merging.")
        else:
            print("❌ Failed to merge PR")
    except Exception as e:
        print(f"Error merging: {e}")

if __name__ == '__main__':
    main()