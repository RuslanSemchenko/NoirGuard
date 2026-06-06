import os
from github import Github, Auth

class GitHubClient:
    def __init__(self, token: str | None = None):
        self.token = token or os.environ.get("GITHUB_TOKEN")
        if not self.token:
            raise ValueError("GITHUB_TOKEN is required.")
        auth = Auth.Token(self.token)
        self.client = Github(auth=auth)

    def comment_on_issue(self, repo_name: str, issue_number: int, comment: str) -> None:
        repo = self.client.get_repo(repo_name)
        issue = repo.get_issue(issue_number)
        issue.create_comment(comment)

    def create_pull_request(self, repo_name: str, pr_config: dict[str, str]) -> None:
        repo = self.client.get_repo(repo_name)
        repo.create_pull(title=pr_config["title"],
                         body=pr_config["body"],
                         head=pr_config["head"],
                         base=pr_config["base"])
