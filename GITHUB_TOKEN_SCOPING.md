# GitHub Token Scoping Explanation

## The Issue

You created a GitHub Personal Access Token (PAT) for "just one repo," but the agent is still able to access details from other repositories. This is happening because of how GitHub tokens work.

## How GitHub Tokens Actually Work

### Token Scopes vs Repository Access

**Important**: GitHub Personal Access Tokens don't restrict access to a single repository. Instead, they grant permissions based on **scopes**:

- **`repo` scope**: Grants access to ALL repositories you have access to:
  - Your own repositories
  - Repositories you're a collaborator on
  - Organization repositories (if you're a member)
  - Public repositories (read access)

- **`public_repo` scope**: Grants read/write access to public repositories

- **Fine-grained tokens**: Newer token type that CAN restrict to specific repositories, but requires different setup

### Why You're Seeing Other Repos

Even with `user:{username}` qualifier in search queries, GitHub's search API can return results from:

1. **Public repositories** - If your token has `public_repo` or `repo` scope, you can search public code
2. **Repositories you collaborate on** - If you're a collaborator, those repos are accessible
3. **Organization repositories** - If you're a member of an organization, those repos are accessible

The `user:{username}` qualifier only limits results to repositories **owned by** that username, but doesn't prevent access to repos you have permissions for through other means.

## The Solution

I've added **post-filtering** to ensure only results from repositories owned by the authenticated user are returned:

### 1. Enhanced User Scoping

The code now:
- Always gets the authenticated user's username first
- Uses `user:{username}` qualifier in all search queries
- Logs warnings when searches aren't properly scoped

### 2. Result Filtering

Added a `_is_user_repo()` method that:
- Checks if each result belongs to the authenticated user's repository
- Extracts repository ownership from various response formats:
  - `repository.full_name` (e.g., "username/repo-name")
  - `repository.owner.login`
  - `full_name` field
  - Path-based extraction
- **Filters out** any results not owned by the authenticated user

### 3. Logging

The code now logs:
- When results are filtered out
- How many items were filtered
- Warnings when searches aren't scoped to user

## How to Restrict to a Single Repository

If you want to restrict access to **only one specific repository**, you have a few options:

### Option 1: Use Fine-Grained Personal Access Token (Recommended)

1. Go to https://github.com/settings/tokens?type=beta
2. Click "Generate new token"
3. Select "Fine-grained personal access token"
4. Under "Repository access", select "Only select repositories"
5. Choose your specific repository
6. Grant only the permissions you need (e.g., "Contents: Read-only")
7. Use this token instead of your classic token

### Option 2: Modify the Code to Filter by Repository Name

You can add an environment variable to restrict to a specific repository:

```env
GITHUB_REPO_FILTER=your-username/your-repo-name
```

Then modify `_is_user_repo()` to also check the repository name.

### Option 3: Use Repository-Specific Scopes (Limited)

Classic tokens don't support repository-specific scoping. You must use fine-grained tokens for this.

## Current Behavior

With the latest changes:

1. ✅ All searches are scoped to `user:{your-username}`
2. ✅ Results are filtered to only include items from your repositories
3. ✅ Items from other users' repos are excluded
4. ⚠️ Items from repos you collaborate on (but don't own) may still appear if they match the search

## Testing

To verify the filtering is working:

1. Check the backend logs - you should see messages like:
   ```
   Scoping code search to user premdwivedi's repositories ONLY: user:premdwivedi keywords
   Filtered 5 items not from user premdwivedi's repositories
   ```

2. Try a search query and verify only your repos appear in results

3. Check the citations in the UI - they should only reference your repositories

## Recommendations

1. **Use Fine-Grained Tokens**: For production, use fine-grained tokens with repository-specific access
2. **Monitor Logs**: Check backend logs to see what's being filtered
3. **Test Queries**: Try various queries to ensure only your repos appear
4. **Review Token Permissions**: Check your token's scopes at https://github.com/settings/tokens

## Summary

- GitHub tokens grant access based on **scopes**, not individual repositories
- The `user:{username}` qualifier helps but doesn't fully restrict access
- I've added **result filtering** to ensure only your repositories appear in results
- For true single-repo access, use **fine-grained tokens** with repository selection



