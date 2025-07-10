#!/usr/bin/env python3
"""
Test YOLO achievement with pending review - the correct way
"""

from github import Github, Auth
import time
from datetime import datetime

# Configuration
TOKEN = 'YOUR_GITHUB_TOKEN_HERE'
REPO_NAME = 'yolo-achievement-test-repo'
REVIEWER = 'YOUR_COLLABORATOR_USERNAME'  # You'll need to add a collaborator or use someone who has access

def main():
    print("Starting YOLO achievement test with pending review...")
    
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
    
    # Get repository
    repo_full_name = f"{username}/{REPO_NAME}"
    try:
        repo = g.get_repo(repo_full_name)
        print(f"Using existing repository: {repo_full_name}")
    except Exception as e:
        print(f"Repository not found: {e}")
        print("Please create the repository first")
        return
    
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
        title='YOLO Achievement PR - With Pending Review',
        body='This PR will be merged with a pending review for the YOLO achievement! 🎯',
        base=default_branch,
        head=branch_name
    )
    
    print(f"Created PR #{pr.number}")
    
    # Request a review
    print(f"Requesting review from: {REVIEWER}")
    try:
        pr.create_review_request(reviewers=[REVIEWER])
        print("Review requested successfully!")
    except Exception as e:
        print(f"Failed to request review: {e}")
        print("Note: The reviewer must be a collaborator or have access to the repo")
        # Try to continue anyway - you might be able to self-review
    
    time.sleep(2)
    
    # Merge with pending review
    print(f"Merging PR #{pr.number} with pending review...")
    try:
        merge_result = pr.merge(
            merge_method='merge',
            commit_title=f'Merge PR #{pr.number}: YOLO Achievement with Pending Review',
            commit_message='Merged with pending review for YOLO achievement!'
        )
        
        if merge_result.merged:
            print(f"✅ Successfully merged PR #{pr.number} with pending review!")
            print(f"PR URL: {pr.html_url}")
            print("\nYOLO achievement should be unlocked! Check your GitHub profile.")
        else:
            print("❌ Failed to merge PR")
    except Exception as e:
        print(f"Error merging: {e}")
        print("Note: The repository might have branch protection rules preventing merge")

if __name__ == '__main__':
    main()