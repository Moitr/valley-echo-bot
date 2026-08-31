# basic-bot

## Browser screenshots

截图使用 Playwright，支持 Chromium、Firefox 和 WebKit。默认 `browser.browser = "auto"`：
优先使用系统浏览器，没有可用浏览器时使用 Playwright 管理的浏览器。

安装 Python 依赖后，在服务器执行一次浏览器运行时安装：

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
```

如果服务器还没有系统依赖（常见于精简 Linux 镜像），使用：

```bash
python -m playwright install --with-deps chromium
```

配置文件中的 `browser.browser` 可设为 `auto`、`chromium`、`firefox` 或 `webkit`，
`browser.path` 可指定对应浏览器的可执行文件路径。
