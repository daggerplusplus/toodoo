const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs');

const PROMPT_HTML = path.join(__dirname, 'prompt.html');
const CONFIG_FILE = path.join(app.getPath('userData'), 'config.json');

function loadServerUrl() {
  try {
    const raw = fs.readFileSync(CONFIG_FILE, 'utf-8');
    const config = JSON.parse(raw);
    return config.serverUrl || '';
  } catch {
    return '';
  }
}

function saveServerUrl(url) {
  const config = { serverUrl: url };
  fs.writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2), 'utf-8');
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
  let serverUrl = loadServerUrl();

  if (!serverUrl) {
    serverUrl = await promptServerUrl();
    if (!serverUrl) {
      app.quit();
      return;
    }
    saveServerUrl(serverUrl);
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

  win.loadURL(serverUrl + '/electron-login');
  win.show();
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
