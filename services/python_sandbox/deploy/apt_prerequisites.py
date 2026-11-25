"""Install sandbox prerequisites using temporary, signed official APT sources.

Does not edit /etc/apt or update its shared index/cache. --check downloads and
resolves the same packages without installing anything or requiring root.
"""
import argparse
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import subprocess
import tempfile
import time
from urllib.parse import urlsplit

PACKAGES = ('uidmap', 'dbus-user-session', 'python3-venv', 'slirp4netns')


def official_sources(release, architecture):
    distro, codename = release['ID'], release.get('VERSION_CODENAME', '')
    if not re.fullmatch(r'[a-z][a-z0-9-]+', codename) or not re.fullmatch(r'[a-z0-9]+', architecture):
        raise ValueError('A valid distribution codename and native architecture are required.')
    if distro == 'debian':
        components = 'main'
        keyring = '/usr/share/keyrings/debian-archive-keyring.gpg'
        mirrors = [('https://deb.debian.org/debian', f'{codename} {codename}-updates'),
                   ('https://security.debian.org/debian-security', f'{codename}-security')]
    elif distro == 'ubuntu':
        components = 'main universe'
        keyring = '/usr/share/keyrings/ubuntu-archive-keyring.gpg'
        if architecture in ('amd64', 'i386'):
            mirrors = [('https://archive.ubuntu.com/ubuntu', f'{codename} {codename}-updates'),
                       ('https://security.ubuntu.com/ubuntu', f'{codename}-security')]
        else:
            mirrors = [('https://ports.ubuntu.com/ubuntu-ports', f'{codename} {codename}-updates {codename}-security')]
    else:
        raise ValueError('Automatic prerequisite installation supports Debian and Ubuntu only.')
    sources = '\n'.join(f'Types: deb\nURIs: {url}\nSuites: {suites}\nComponents: {components}\n'
                        f'Architectures: {architecture}\nSigned-By: {keyring}\n' for url, suites in mirrors)
    return sources, keyring


def configure(directory, sources, proxy='', check=False):
    if proxy:
        parsed = urlsplit(proxy)
        if (parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost')
                or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment
                or not parsed.port):
            raise ValueError('Proxy must be a credential-free loopback HTTP address with a port.')
    # Public package metadata only; _apt must be able to traverse this directory.
    directory.chmod(0o755)
    for name in ('empty', 'lists', 'cache', 'cache/archives'):
        (directory / name).mkdir(mode=0o755)
        (directory / name).chmod(0o755)
    source = directory / 'official.sources'
    source.write_text(sources)
    source.chmod(0o644)
    settings = {
        'Dir::Etc::main': '/dev/null', 'Dir::Etc::parts': str(directory / 'empty'),
        'Dir::Etc::sourcelist': str(source), 'Dir::Etc::sourceparts': str(directory / 'empty'),
        'Dir::Etc::preferences': '/dev/null', 'Dir::Etc::preferencesparts': str(directory / 'empty'),
        'Dir::State::lists': str(directory / 'lists'), 'Dir::Cache': str(directory / 'cache'),
        # apt 3.0.3 can accumulate huge delayed-retry warning queues (#1111554).
        # Retry entire download-only commands below, never an installation.
        'Acquire::Languages': 'none', 'Acquire::Retries': '0',
        'Acquire::http::Timeout': '25', 'Acquire::https::Timeout': '25',
        'APT::Update::Error-Mode': 'any', 'APT::Get::AllowUnauthenticated': 'false',
        'Acquire::AllowInsecureRepositories': 'false',
        'Acquire::AllowDowngradeToInsecureRepositories': 'false',
    }
    if proxy:
        settings.update({'Acquire::http::Proxy': proxy, 'Acquire::https::Proxy': proxy})
    if check:
        # No writes or lock acquisition in the system package database during checks.
        extended = directory / 'extended_states'
        if Path('/var/lib/apt/extended_states').exists():
            shutil.copyfile('/var/lib/apt/extended_states', extended)
        settings.update({'Dir::State::extended_states': str(extended), 'Debug::NoLocking': 'true'})
    config = directory / 'apt.conf'
    config.write_text(''.join(f'{key} "{value}";\n' for key, value in settings.items()))
    config.chmod(0o644)
    # APT_CONFIG loads before /etc/apt/apt.conf.d, so global hooks and sources
    # never enter this process. No insecure or unsigned fallback is attempted.
    return dict(os.environ, APT_CONFIG=str(config), DEBIAN_FRONTEND='noninteractive')


def seed_cached_lists(directory, sources):
    """Reuse root-owned official indexes, then let apt update/revalidate them."""
    prefixes = []
    for stanza in sources.strip().split('\n\n'):
        fields = dict(line.split(': ', 1) for line in stanza.splitlines())
        uri = urlsplit(fields['URIs'])
        base = (uri.netloc + uri.path).replace('/', '_').rstrip('_')
        prefixes.extend(f'{base}_dists_{suite}_' for suite in fields['Suites'].split())
    count = 0
    for source in Path('/var/lib/apt/lists').iterdir():
        metadata = source.lstat()
        if (not any(source.name.startswith(prefix) for prefix in prefixes)
                or not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != 0
                or metadata.st_mode & 0o022):
            continue
        shutil.copy2(source, directory / 'lists' / source.name)
        count += 1
    return count


def download(command, env):
    for attempt in range(3):
        try:
            subprocess.run(command, env=env, check=True)
            return
        except subprocess.CalledProcessError:
            if attempt == 2:
                raise
            print(f'APT download failed; retrying with existing verified cache ({attempt + 2}/3).', flush=True)
            time.sleep(attempt + 1)


def prerequisites_installed():
    status = subprocess.run(['dpkg-query', '-W', '-f=${db:Status-Abbrev}\\n', *PACKAGES],
                            capture_output=True, text=True, check=False)
    lines = status.stdout.splitlines()
    return status.returncode == 0 and len(lines) == len(PACKAGES) and all(line == 'ii ' for line in lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proxy', default='')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if not args.check and os.geteuid() != 0:
        parser.error('Installation requires sudo; --check does not.')
    if not args.check and prerequisites_installed():
        print('APT prerequisites already installed; skipping package update/download/install.', flush=True)
        return
    architecture = subprocess.check_output(['dpkg', '--print-architecture'], text=True).strip()
    sources, keyring = official_sources(platform.freedesktop_os_release(), architecture)
    if not Path(keyring).is_file():
        parser.error('Install the distribution archive keyring first; signature checks cannot be skipped.')
    with tempfile.TemporaryDirectory(prefix='enzymind-apt-', dir='/tmp') as temporary:
        directory = Path(temporary)
        env = configure(directory, sources, args.proxy, args.check)
        cached = seed_cached_lists(directory, sources)
        print('APT: temporary official sources, isolated indexes/cache, signature verification enabled.', flush=True)
        print(f'APT: revalidating {cached} root-owned cached official indexes.', flush=True)
        download(['apt-get', 'update'], env)
        command = ['apt-get', '--no-upgrade', '--no-remove', '--no-install-recommends']
        if args.check:
            subprocess.run([*command, '--simulate', 'install', *PACKAGES], env=env, check=True)
        download([*command, '--download-only', '-y', 'install', *PACKAGES], env)
        if args.check:
            archives = list((directory / 'cache/archives').glob('*.deb'))
            print(f'APT check passed: {len(archives)} packages downloaded; none installed.', flush=True)
        else:
            # All archives are verified and cached. Run dpkg exactly once;
            # download retries can never replay partially executed maintainer scripts.
            subprocess.run([*command, '--no-download', '-y', 'install', *PACKAGES], env=env, check=True)


if __name__ == '__main__':
    main()
