# Upload the entire Crochet Craft project without Git

Target: https://github.com/crochet-flowers-patterns-craft/crochet-flowers-patterns-craft.github.io

## One-time token setup

1. Open https://github.com/settings/personal-access-tokens/new.
2. Name the token `Crochet website upload` and choose a short expiration.
3. Select the resource owner `crochet-flowers-patterns-craft`.
4. Under Repository access, choose Only select repositories, then `crochet-flowers-patterns-craft.github.io`.
5. Under Repository permissions, set Contents to Read and write. Metadata is included automatically.
6. Generate and copy the token. If the owner is an organization, its token policy may require approval first.

## Upload

Double-click `Upload-to-GitHub.cmd`. Paste your token into the terminal prompt and press Enter. The token is hidden while entered and is not saved to a file. Keep the window open until Success appears. The first upload may take several minutes.

Python is already installed on this computer. The uploader uses only Python's standard library; Git and extra packages are unnecessary.

The upload includes all website pages, the entire assets and articles directories, posts.js, authoring scripts/data when present, and these uploader files. Editor settings, preview screenshots, credentials, caches, and old homepage backups are excluded. All website files are preserved in their proper folders. Existing remote files with matching names are updated; unrelated remote files are retained. There is no force push.

To inspect the upload locally without entering a token or contacting GitHub:

```powershell
python upload_to_github.py --dry-run
```

The uploader sends the files through GitHub's API and saves all changes in one commit. If interrupted, run it again. It skips files already committed and checks for changes to the branch during upload. Empty repositories are initialized automatically with a small first commit, then all remaining project files are saved in one upload commit. You do not need to create a README manually.

## Publish on GitHub Pages

After uploading, open the repository's Settings > Pages. Under Build and deployment, select Deploy from a branch, select `main`, select `/ (root)`, and click Save.

The intended website address is https://crochet-flowers-patterns-craft.github.io/ once GitHub Pages finishes its deployment. The uploader uploads files but does not change Pages settings.

## Troubleshooting

- HTTP 401: the token is invalid or expired.
- HTTP 403: check Contents permissions, organization approval, branch protection, or rate limits.
- HTTP 404: check resource owner and repository selection.
- If the terminal cannot hide token input, use the supplied double-click launcher in a normal Windows terminal.

Never put a token into these files or paste it into chat.
