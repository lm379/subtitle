# BilibiliPotPlayer Danmaku Server

> 本项目重写自 [chen310](https://github.com/chen310) 的 Replit 仓库，旨在为 [BilibiliPotPlayer](https://github.com/chen310/BilibiliPotPlayer) 提供稳定的弹幕代理服务。

## ✨ 项目简介

这是一个基于 Next.js 构建的弹幕代理服务，支持部署在 Vercel、Netlify、Cloudflare Pages、EdgeOne Pages 等多种 Serverless 平台。通过自行部署，你可以拥有更稳定、可控的弹幕服务体验。

## 🚀 功能特性

- **弹幕代理**：为 PotPlayer 播放 B 站视频提供实时弹幕支持。
- **多平台支持**：兼容所有支持 Next.js 的部署平台（Vercel, Netlify, Cloudflare, EdgeOne 等）。

## 📋 前置要求

在开始之前，请确保你满足以下条件：

1. **已安装 BilibiliPotPlayer 插件**：
   本项目是该插件的服务端配套设施，请先确保客户端插件已安装。
   - [前往原项目下载安装](https://github.com/chen310/BilibiliPotPlayer)
2. **拥有一个自定义域名**：
   为了连接服务，你需要拥有一个可以配置 CNAME 的域名。

## 🛠️ 部署教程

本项目支持多种平台部署，以下以 **EdgeOne Pages** 为例：

### 1. 获取代码
点击右上角的 `Fork` 按钮，将本项目克隆到你的 GitHub 仓库。

### 2. 创建项目
在 EdgeOne Pages 控制台连接你的 GitHub 账号，选择刚刚 Fork 的项目进行部署。
> ⚠️ **注意**：如果你的域名未备案，加速区域请务必选择 **「全球可用区（不含中国大陆）」**，否则无法绑定自定义域名。

### 3. 配置域名
在 EdgeOne Pages 项目设置中添加你的自定义域名（例如 `danmu.yourdomain.com`），并按照提示配置 CNAME 记录和 HTTPS 证书。

### 4. 验证部署
访问你的自定义域名（如 `https://danmu.yourdomain.com`），如果页面显示 `success`，说明服务已部署成功。

## ⚙️ 客户端配置

部署完成后，需要修改本地的 `Bilibili_Config.json` 文件以连接到你的服务器。

1. 打开 `Bilibili_Config.json` 配置文件。
2. 找到 `server` 字段。
3. 将其修改为你部署的域名：

**修改前：**
```json
"server": "https://subtitle.chen310.repl.co"
```

**修改后：**
```json
"server": "https://danmu.yourdomain.com"
```

4. 重启 PotPlayer 播放器使配置生效。

---

*感谢原作者 [chen310](https://github.com/chen310) 的开源贡献。*
