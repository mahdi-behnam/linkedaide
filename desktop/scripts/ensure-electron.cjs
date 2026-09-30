#!/usr/bin/env node
/**
 * Self-healing Electron binary verifier & installer for LinkedIn HITL Desktop.
 * 
 * Automatically ensures:
 * 1. The platform Electron binary (electron.exe / electron) exists and is executable.
 * 2. node_modules/electron/path.txt contains clean platform path without \r\n linebreaks.
 * 3. node_modules/electron/index.js is patched to trim path.txt.
 * 4. Missing binaries are unpacked automatically from cache or downloaded via mirror.
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const platformPath = process.platform === 'win32' 
  ? 'electron.exe' 
  : (process.platform === 'darwin' ? 'Electron.app/Contents/MacOS/Electron' : 'electron');

const electronDir = path.join(__dirname, '..', 'node_modules', 'electron');
const distDir = path.join(electronDir, 'dist');
const exePath = path.join(distDir, platformPath);
const pathTxt = path.join(electronDir, 'path.txt');
const indexPath = path.join(electronDir, 'index.js');

function patchIndexJs() {
  if (fs.existsSync(indexPath)) {
    try {
      let content = fs.readFileSync(indexPath, 'utf-8');
      if (!content.includes('.trim()')) {
        content = content.replace("fs.readFileSync(pathFile, 'utf-8')", "fs.readFileSync(pathFile, 'utf-8').trim()");
        fs.writeFileSync(indexPath, content, 'utf-8');
      }
    } catch {
      // Non-fatal
    }
  }
}

function isElectronReady() {
  if (!fs.existsSync(exePath) || !fs.existsSync(pathTxt)) {
    return false;
  }
  try {
    const rawPath = fs.readFileSync(pathTxt, 'utf-8');
    // If path.txt contains carriage returns or wrong content, fix it
    if (rawPath.includes('\r') || rawPath.includes('\n') || rawPath.trim() !== platformPath) {
      fs.writeFileSync(pathTxt, platformPath.trim(), 'utf-8');
    }
    patchIndexJs();
    return true;
  } catch {
    return false;
  }
}

function findCachedZip() {
  const localAppData = process.env.LOCALAPPDATA || (process.env.USERPROFILE ? path.join(process.env.USERPROFILE, 'AppData', 'Local') : '');
  const home = process.env.HOME || process.env.USERPROFILE || '';
  
  const possibleCacheDirs = [
    localAppData ? path.join(localAppData, 'electron', 'Cache') : null,
    home ? path.join(home, '.cache', 'electron') : null,
    home ? path.join(home, 'AppData', 'Local', 'electron', 'Cache') : null,
    home ? path.join(home, 'Library', 'Caches', 'electron') : null,
  ].filter(Boolean);

  function findZip(dir) {
    if (!fs.existsSync(dir)) return null;
    try {
      for (const file of fs.readdirSync(dir, { withFileTypes: true })) {
        const full = path.join(dir, file.name);
        if (file.isDirectory()) {
          const found = findZip(full);
          if (found) return found;
        } else if (file.name.endsWith('.zip') && file.name.includes('electron-v')) {
          return full;
        }
      }
    } catch {
      // Ignore read errors
    }
    return null;
  }

  for (const cacheDir of possibleCacheDirs) {
    const zipPath = findZip(cacheDir);
    if (zipPath) return zipPath;
  }
  return null;
}

async function extractZip(zipPath) {
  if (!fs.existsSync(distDir)) {
    fs.mkdirSync(distDir, { recursive: true });
  }

  // 1. Try Python zipfile if available (most reliable across Windows paths)
  try {
    execSync(`python -m zipfile -e "${zipPath}" "${distDir}"`, { stdio: 'ignore' });
    if (fs.existsSync(exePath)) {
      return true;
    }
  } catch {
    // Fall back to extract-zip
  }

  // 2. Try extract-zip npm module
  try {
    const extract = require('extract-zip');
    let count = 0;
    await extract(zipPath, {
      dir: distDir,
      onEntry: () => {
        count++;
        if (count % 25 === 0) {
          process.stdout.write(`\rUnpacking Electron binaries... (${count} files)`);
        }
      }
    });
    process.stdout.write('\n');
    return fs.existsSync(exePath);
  } catch (err) {
    console.warn('extract-zip fallback warning:', err.message);
    return false;
  }
}

async function main() {
  if (!fs.existsSync(electronDir)) {
    console.error('node_modules/electron does not exist. Run "npm install" first.');
    process.exit(1);
  }

  if (isElectronReady()) {
    // Fast exit if already properly configured
    return;
  }

  console.log('Verifying Electron binary installation...');

  let zipPath = findCachedZip();
  if (!zipPath) {
    console.log('Downloading Electron prebuilt binary via global mirror...');
    try {
      execSync('node install.js', {
        cwd: electronDir,
        env: {
          ...process.env,
          ELECTRON_MIRROR: 'https://npmmirror.com/mirrors/electron/',
        },
        stdio: 'inherit',
      });
      zipPath = findCachedZip();
    } catch {
      // If install.js failed, try to continue
    }
  }

  if (zipPath && !fs.existsSync(exePath)) {
    console.log(`Found cached archive: ${path.basename(zipPath)}`);
    console.log('Unpacking into dist directory...');
    await extractZip(zipPath);
  }

  // Ensure path.txt is correctly written without newlines
  fs.writeFileSync(pathTxt, platformPath.trim(), 'utf-8');
  patchIndexJs();

  if (fs.existsSync(exePath)) {
    console.log(`Electron verified at: ${exePath}`);
  } else {
    console.error(`Error: Could not locate ${exePath} after installation attempt.`);
    process.exit(1);
  }
}

main().catch(err => {
  console.error('Electron verification failed:', err);
  process.exit(1);
});
