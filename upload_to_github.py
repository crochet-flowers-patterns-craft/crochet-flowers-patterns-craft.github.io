#!/usr/bin/env python3
"""Upload this static project to GitHub using HTTPS only. No Git installation needed."""
import argparse
import base64
import getpass
import hashlib
import json
from pathlib import Path
import sys
import time
import warnings
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

OWNER = 'crochet-flowers-patterns-craft'
REPO = 'crochet-flowers-patterns-craft.github.io'
ROOT = Path(__file__).resolve().parent
ROOT_FILES = {'index.html', 'about.html', 'contact.html', 'privacy.html', 'terms.html',
              'posts.js', 'README.md', 'README-upload.md', '.nojekyll',
              'upload_to_github.py', 'Upload-to-GitHub.cmd'}
DIRECTORIES = {'assets', 'articles', 'scripts', 'data'}
EXCLUDED_PARTS = {'.git', '.vscode', '.qa', '.codex', '.agents', '.aws', 'node_modules', '__pycache__'}

class UploadError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def project_files(root=ROOT):
    files = []
    for file in root.rglob('*'):
        if not file.is_file():
            continue
        relative = file.relative_to(root)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if file.is_symlink() or not file.resolve().is_relative_to(root.resolve()):
            raise UploadError(f'File points outside the project: {relative.as_posix()}')
        if len(relative.parts) == 1:
            include = relative.name in ROOT_FILES
        else:
            include = relative.parts[0] in DIRECTORIES
        if not include:
            continue
        # Authoring/deployment files only; never include credential/configuration files.
        if file.name.startswith('.') and file.name != '.nojekyll':
            continue
        if file.suffix.lower() in {'.pem', '.key', '.pfx', '.p12', '.env', '.pyc'}:
            continue
        if file.name.lower() in {'credentials', 'credentials.json', 'secrets.json', 'token.txt'}:
            continue
        if file.stat().st_size >= 100 * 1024 * 1024:
            raise UploadError(f'File is too large for a normal GitHub repository: {relative.as_posix()}')
        files.append((relative.as_posix(), file))
    if not (root / 'index.html').is_file():
        raise UploadError('index.html was not found beside the uploader.')
    return sorted(files)


def blob_sha(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode('ascii') + b'\0' + data).hexdigest()


class GitHub:
    def __init__(self, token):
        self.token = token
        self.base = f'https://api.github.com/repos/{OWNER}/{REPO}'
        self.last_write = 0.0

    def request(self, method, route='', payload=None):
        # Serialize writes and stay below GitHub's secondary write-rate limit.
        if method != 'GET':
            delay = 1.1 - (time.monotonic() - self.last_write)
            if delay > 0:
                time.sleep(delay)
            self.last_write = time.monotonic()
        data = None if payload is None else json.dumps(payload).encode('utf-8')
        req = Request(self.base + route, data=data, method=method, headers={
            'Authorization': 'Bearer ' + self.token,
            'Accept': 'application/vnd.github+json',
            'Content-Type': 'application/json',
            'User-Agent': 'Crochet-Craft-Static-Uploader',
            'X-GitHub-Api-Version': '2026-03-10',
        })
        try:
            with urlopen(req, timeout=120) as response:
                return json.load(response)
        except HTTPError as error:
            try:
                detail = json.loads(error.read().decode('utf-8')).get('message', '')
            except Exception:
                detail = ''
            if error.code == 401:
                hint = 'The token is invalid or expired. Create a new token and run again.'
            elif error.code == 403:
                hint = 'Check Contents: Read and write permission, owner approval, and branch rules. If rate-limited, wait and run again.'
            elif error.code == 404:
                hint = 'Check the token resource owner and repository selection.'
            elif error.code in (409, 422):
                hint = 'Check whether main exists, is protected, or changed during upload; then run again.'
            else:
                hint = 'Run again when the connection or GitHub service is available.'
            raise UploadError(f'GitHub HTTP {error.code}: {detail}\n{hint}', status=error.code) from None
        except (URLError, TimeoutError, OSError) as error:
            raise UploadError('The GitHub connection failed. Run again; the uploader skips files already committed.') from None



def get_or_initialize_head(files, api, branch):
    route = '/git/ref/heads/' + quote(branch, safe='')
    try:
        return api.request('GET', route)['object']['sha']
    except UploadError as error:
        if error.status not in (404, 409):
            raise
        # A missing default branch is not proof that the whole repository is empty.
        # Only initialize when GitHub confirms there are no branches.
        branches = api.request('GET', '/branches?per_page=1')
        if branches != []:
            raise error
    print('The repository is empty. Creating its initial commit automatically...', flush=True)
    seed_name, seed_file = next(
        ((name, file) for name, file in files if name == 'README-upload.md'), files[0])
    seed = seed_file.read_bytes()
    try:
        created = api.request('PUT', '/contents/' + quote(seed_name, safe='/'), {
            'message': 'Initialize Crochet Craft repository',
            'content': base64.b64encode(seed).decode('ascii'),
            'branch': branch,
        })
    except UploadError as error:
        # The write can finish despite a timeout, or another writer can initialize first.
        try:
            return api.request('GET', route)['object']['sha']
        except UploadError:
            raise error
    if created.get('content', {}).get('sha') != blob_sha(seed):
        raise UploadError('The initial file checksum could not be verified.')
    return api.request('GET', route)['object']['sha']


def upload(files, api):
    info = api.request('GET')
    branch = info['default_branch']
    ref_route = '/git/refs/heads/' + quote(branch, safe='')
    head = get_or_initialize_head(files, api, branch)
    commit = api.request('GET', '/git/commits/' + head)
    base_tree = commit['tree']['sha']
    remote = api.request('GET', '/git/trees/' + base_tree + '?recursive=1')
    if remote.get('truncated'):
        raise UploadError('The repository tree is too large to verify safely.')
    existing = {item['path']: item['sha'] for item in remote['tree'] if item['type'] == 'blob'}
    known_blobs = set(existing.values())
    changes = []
    skipped = 0
    print(f'Uploading to {info["full_name"]}, branch {branch}.', flush=True)
    for number, (relative, file) in enumerate(files, 1):
        data = file.read_bytes()
        sha = blob_sha(data)
        if existing.get(relative) == sha:
            skipped += 1
            print(f'[{number}/{len(files)}] Already current: {relative}', flush=True)
            continue
        if sha not in known_blobs:
            result = api.request('POST', '/git/blobs', {
                'encoding': 'base64', 'content': base64.b64encode(data).decode('ascii')})
            if result.get('sha') != sha:
                raise UploadError(f'GitHub returned an unexpected checksum for {relative}.')
            known_blobs.add(sha)
        changes.append({'path': relative, 'mode': '100644', 'type': 'blob', 'sha': sha})
        print(f'[{number}/{len(files)}] Uploaded: {relative}', flush=True)
    if not changes:
        print('Everything is already up to date. No new commit needed.')
        return
    # Keep unrelated remote files and refuse to overwrite concurrent branch changes.
    latest = api.request('GET', '/git/ref/heads/' + quote(branch, safe=''))['object']['sha']
    if latest != head:
        raise UploadError('The repository changed during upload. Run again to include its latest changes.')
    tree = api.request('POST', '/git/trees', {'base_tree': base_tree, 'tree': changes})
    saved = api.request('POST', '/git/commits', {
        'message': 'Upload static Crochet Craft website', 'tree': tree['sha'], 'parents': [head]})
    try:
        api.request('PATCH', ref_route, {'sha': saved['sha'], 'force': False})
    except UploadError:
        # A timeout can occur after GitHub accepts the update. Check before reporting failure.
        current = api.request('GET', '/git/ref/heads/' + quote(branch, safe=''))['object']['sha']
        if current != saved['sha']:
            raise
    verified = api.request('GET', '/git/trees/' + tree['sha'] + '?recursive=1')
    if verified.get('truncated'):
        raise UploadError('The upload was committed, but its full tree could not be verified.')
    uploaded = {item['path']: item['sha'] for item in verified['tree'] if item['type'] == 'blob'}
    if any(uploaded.get(item['path']) != item['sha'] for item in changes):
        raise UploadError('The upload was committed, but final file verification failed.')
    print(f'\nSuccess: {len(changes)} files saved in one commit; {skipped} already current.')
    print(f'https://github.com/{OWNER}/{REPO}/commit/{saved["sha"]}')
    print('To publish: repository Settings > Pages > Deploy from a branch > ' + branch + ' > / (root) > Save.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', help='List files locally; do not request a token or contact GitHub.')
    args = parser.parse_args()
    files = project_files()
    size = sum(file.stat().st_size for _, file in files)
    print(f'Project: {ROOT}')
    print(f'Target: https://github.com/{OWNER}/{REPO}')
    print(f'{len(files)} files, {size / (1024 * 1024):.1f} MiB. Folder structure is preserved.')
    if args.dry_run:
        for relative, _ in files:
            print(relative)
        print('Dry run complete. Nothing was uploaded.')
        return 0
    print('\nThis run uploads the listed project to GitHub. Matching remote paths are updated; unrelated files are preserved.')
    print('Paste your fine-grained token below. It will be hidden and is never saved to disk.')
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        try:
            token = getpass.getpass('GitHub token: ').strip()
        except getpass.GetPassWarning:
            raise UploadError('A private token prompt is unavailable here. Run Upload-to-GitHub.cmd in a normal terminal.') from None
    if not token:
        raise UploadError('No token entered. Nothing was uploaded.')
    upload(files, GitHub(token))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('\nUpload cancelled. You can run the uploader again.')
        sys.exit(130)
    except UploadError as error:
        print('\nERROR: ' + str(error), file=sys.stderr)
        sys.exit(1)
