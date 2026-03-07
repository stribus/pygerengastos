---
name: create-github-pull-request-from-specification
description: 'Create GitHub Pull Request for feature request from specification file using pull_request_template.md template.'
---

# Create GitHub Pull Request from Specification

Create GitHub Pull Request for the specification at `${workspaceFolder}/.github/pull_request_template.md` .

## Process

1. Analyze specification file template from '${workspaceFolder}/.github/pull_request_template.md' to extract requirements by 'search' tool.
2. Create a pull request draft using the `create_pull_request` tool for the `${input:targetBranch}`. Check if a pull request for the current branch already exists using `get_pull_request`. If one exists, continue to step 4 and skip step 3.
3. Get the changes in the pull request using the `get_pull_request_diff` tool to analyze the changed information.
4. Update the pull request body and title created in the previous step using the `update_pull_request` tool. Incorporate the information from the template obtained in the first step to update the body and title as needed.
5. Change the pull request state from draft to ready for review using the `update_pull_request` tool.
6. Use `get_me` to get the username of the person who created the pull request and assign it using the `update_pull_request` tool.
7. Respond with the URL of the created pull request to the user.

## Requirements
- Single pull request for the complete specification
- Clear title/pull_request_template.md identifying the specification
- Fill enough information into pull_request_template.md
- Verify against existing pull requests before creation
