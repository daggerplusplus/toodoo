const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs');

const PROMPT_HTML = path.join(__dirname, 'prompt.html');
const CONFIG_FILE = path.join(app.getPath('userData'), 'config.json');

function loadConfig() {
  try {
    const raw = fs.readFileSync(CONFIG_FILE, 'utf-8');
    return JSON.parse(raw);
  } catch {
    return { serverUrl: '', token: '' };
  }
}

function saveConfig(config) {
  fs.writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2), 'utf-8');
}

async function verifyToken(serverUrl, token) {
  try {
    const res = await fetch(serverUrl + '/api/me', {
      headers: { Authorization: 'Bearer ' + token },
    });
    return res.ok;
  } catch {
    return false;
  }
}

function promptServerUrl() {
  return new Promise((resolve) => {
    const promptWin = new BrowserWindow({
      width: 400,
      height: 200,
      parent: null,
      show: false,
      webPreferences: {
        nodeIntegration: true,
        contextIsolation: false,
      },
    });

    promptWin.loadFile(PROMPT_HTML);

    const handler = (_event, url) => {
      promptWin.close();
      ipcMain.removeListener('server-url', handler);
      resolve(url);
    };
    ipcMain.on('server-url', handler);

    promptWin.on('closed', () => {
      ipcMain.removeListener('server-url', handler);
      resolve(null);
    });

    promptWin.show();
  });
}

async function createWindow() {
  let config = loadConfig();
  let serverUrl = config.serverUrl || '';

  if (!serverUrl) {
    serverUrl = await promptServerUrl();
    if (!serverUrl) {
      app.quit();
      return;
    }
  }

  // Normalize: remove trailing slash
  serverUrl = serverUrl.replace(/\/+$/, '');

  const win = new BrowserWindow({
    width: 1000,
    height: 700,
    title: 'Toodoo',
    titleBarStyle: 'hiddenInset',
    show: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  // Try to auto-login with saved token
  if (config.token) {
    const valid = await verifyToken(serverUrl, config.token);
    if (valid) {
      win.loadURL(serverUrl + '/');
      win.show();
      return;
    }
  }

  // Show login page, then store the token after successful login
  win.loadURL(serverUrl + '/electron-login');
  win.show();

  // Listen for the login page to report a successful login
  ipcMain.on('electron-login-success', (_event, data) => {
    saveConfig({ serverUrl, token: data.token });
  });
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
